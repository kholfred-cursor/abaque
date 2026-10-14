import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "../../shared/api/ApiContext";
import { call, filenameFrom, saveBlob } from "../../shared/api/call";
import { ApiError, toApiError } from "../../shared/api/errors";
import { fr } from "../../shared/i18n/fr";
import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { ConfirmPanel } from "../../shared/ui/ConfirmPanel";
import { QrCode, qrSvgDocument } from "../../shared/ui/QrCode";
import { publicLink, useEvaluation, type VersionSummary } from "./context";
import styles from "./evaluations.module.css";
import { StatusBadge } from "./StatusBadge";

type Action = "open" | "close" | "reopen" | "archive";
type Message = { tone: "danger" | "success"; text: string };

/** Ballot counts refresh while a version is open (session dashboard: polling, no websocket). */
export const REFRESH_MS = 10_000;

const ACTIONS: Record<VersionSummary["status"], readonly Action[]> = {
  draft: ["open", "archive"],
  open: ["close"],
  closed: ["reopen", "archive"],
  archived: [],
};
const CONFIRM: Partial<Record<Action, string>> = {
  close: fr.versions.confirmClose,
  archive: fr.versions.confirmArchive,
};

const messageOf = (reason: unknown) =>
  reason instanceof ApiError ? reason.message : fr.errors.GENERIC;

function SharePanel({ slug }: { slug: string }) {
  const link = publicLink(slug);
  const [copied, setCopied] = useState(false);
  return (
    <section className={styles.panel} aria-labelledby="share-title">
      <h2 id="share-title">{fr.versions.link}</h2>
      <div className={styles.share}>
        <div className={styles.form}>
          <p className={styles.toolbarStatus}>{fr.versions.linkHint}</p>
          <a className={styles.link} href={link} target="_blank" rel="noreferrer">
            {link}
          </a>
          <div className={styles.actions}>
            <Button
              variant="secondary"
              onClick={() => {
                void navigator.clipboard?.writeText(link).then(() => setCopied(true));
              }}
            >
              {fr.versions.copy}
            </Button>
            <Button
              variant="secondary"
              onClick={() =>
                saveBlob(
                  new Blob([qrSvgDocument(link)], { type: "image/svg+xml" }),
                  `abaque_${slug}_qr.svg`,
                )
              }
            >
              {fr.versions.qrDownload}
            </Button>
            {copied && <span role="status">{fr.versions.copied}</span>}
          </div>
        </div>
        <QrCode text={link} label={fr.versions.qr} className={styles.qr} />
      </div>
    </section>
  );
}

export function VersionsPage() {
  const { evaluation, reload } = useEvaluation();
  const api = useApi();
  const [message, setMessage] = useState<Message | null>(null);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<{ id: string; action: Action } | null>(null);
  const messageRef = useRef<HTMLDivElement>(null);
  const open = evaluation.versions.find((v) => v.status === "open");

  useEffect(() => {
    if (!open) return;
    const timer = window.setInterval(reload, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [open, reload]);

  function show(next: Message) {
    setMessage(next);
    requestAnimationFrame(() => messageRef.current?.focus());
  }

  async function act(id: string, action: Action) {
    setPending(null);
    setBusy(true);
    try {
      await call(
        api.POST("/api/versions/{version_id}/transitions", {
          params: { path: { version_id: id } },
          body: { action },
        }),
      );
      setMessage(null);
      reload();
    } catch (reason) {
      show({ tone: "danger", text: messageOf(reason) });
    } finally {
      setBusy(false);
    }
  }

  async function duplicate(id: string) {
    setBusy(true);
    try {
      const copy = await call(
        api.POST("/api/versions/{version_id}/duplicate", { params: { path: { version_id: id } } }),
      );
      show({ tone: "success", text: fr.versions.duplicated(copy.label) });
      reload();
    } catch (reason) {
      show({ tone: "danger", text: messageOf(reason) });
    } finally {
      setBusy(false);
    }
  }

  async function exportBallots(version: VersionSummary) {
    setBusy(true);
    try {
      const { data, error, response } = await api.GET(
        "/api/versions/{version_id}/exports/ballots.csv",
        { params: { path: { version_id: version.id } }, parseAs: "blob" },
      );
      if (!response.ok || !data) throw toApiError(response.status, error);
      saveBlob(data, filenameFrom(response, `abaque_${version.label}_ballots.csv`));
    } catch (reason) {
      show({ tone: "danger", text: messageOf(reason) });
    } finally {
      setBusy(false);
    }
  }

  const cancel = useCallback(() => setPending(null), []);

  return (
    <>
      <div className={styles.titleLine}>
        <p>{fr.versions.intro}</p>
        <Button variant="secondary" onClick={reload}>
          {fr.versions.refresh}
        </Button>
      </div>
      {message && (
        <Alert tone={message.tone} ref={messageRef}>
          {message.text}
        </Alert>
      )}
      {open ? (
        <SharePanel slug={evaluation.slug} />
      ) : (
        <p className={styles.toolbarStatus}>{fr.versions.noOpen}</p>
      )}
      {pending && (
        <ConfirmPanel
          title={CONFIRM[pending.action] ?? ""}
          confirmLabel={fr.versions[pending.action]}
          busy={busy}
          onConfirm={() => void act(pending.id, pending.action)}
          onCancel={cancel}
        />
      )}
      <div className={styles.tableWrap}>
        <table className={styles.versions}>
          <thead>
            <tr>
              <th scope="col">{fr.editor.version}</th>
              <th scope="col">{fr.versions.status}</th>
              <th scope="col" className={styles.number}>
                {fr.versions.ballots}
              </th>
              <th scope="col">{fr.versions.actions}</th>
            </tr>
          </thead>
          <tbody>
            {[...evaluation.versions].reverse().map((version) => (
              <tr key={version.id}>
                <th scope="row">{version.label}</th>
                <td>
                  <StatusBadge status={version.status} />
                </td>
                <td className={styles.number}>{version.ballot_count}</td>
                <td>
                  <div className={styles.actions}>
                    {ACTIONS[version.status].map((action) => (
                      <Button
                        key={action}
                        variant={action === "open" || action === "reopen" ? "primary" : "secondary"}
                        disabled={busy}
                        aria-label={`${fr.versions[action]} : ${version.label}`}
                        onClick={() =>
                          CONFIRM[action]
                            ? setPending({ id: version.id, action })
                            : void act(version.id, action)
                        }
                      >
                        {fr.versions[action]}
                      </Button>
                    ))}
                    <Button
                      variant="quiet"
                      disabled={busy}
                      aria-label={`${fr.versions.duplicate} : ${version.label}`}
                      onClick={() => void duplicate(version.id)}
                    >
                      {fr.versions.duplicate}
                    </Button>
                    {version.ballot_count > 0 && (
                      <Button
                        variant="quiet"
                        disabled={busy}
                        aria-label={`${fr.versions.export} : ${version.label}`}
                        onClick={() => void exportBallots(version)}
                      >
                        {fr.versions.export}
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
