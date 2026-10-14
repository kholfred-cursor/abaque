import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";
import { useSearchParams } from "react-router";
import { useApi } from "../../shared/api/ApiContext";
import { call } from "../../shared/api/call";
import { ApiError } from "../../shared/api/errors";
import type { components } from "../../shared/api/schema";
import { scale, type ScaleKey } from "../../shared/design/scale";
import { fr } from "../../shared/i18n/fr";
import { Alert } from "../../shared/ui/Alert";
import { Button } from "../../shared/ui/Button";
import { Field, RadioGroup, TextAreaField } from "../../shared/ui/Field";
import { Spinner } from "../../shared/ui/Spinner";
import uiStyles from "../../shared/ui/ui.module.css";
import { currentVersion, useEvaluation } from "./context";
import {
  addGroup,
  addItem,
  fromContent,
  itemCount,
  moveGroup,
  moveItem,
  moveItemBefore,
  moveItemToGroup,
  removeGroup,
  removeItem,
  renameGroup,
  toPayload,
  updateItem,
  validate,
  type Draft,
  type DraftError,
} from "./editorState";
import styles from "./evaluations.module.css";
import { StatusBadge } from "./StatusBadge";

type Content = components["schemas"]["VersionContentResponse"];
type Labels = Partial<Record<ScaleKey, string>>;
type Message = { tone: "danger" | "success"; text: string; reload?: boolean };

const snapshot = (draft: Draft, labels: Labels) => JSON.stringify([toPayload(draft), labels]);
const messageOf = (reason: unknown) =>
  reason instanceof ApiError ? reason.message : fr.errors.GENERIC;
/** Read a chosen file as UTF-8 text (FileReader works in every browser). */
function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(reader.error ?? new Error("read failed"));
    reader.readAsText(file, "utf-8");
  });
}
const focusSoon = (id: string) => requestAnimationFrame(() => document.getElementById(id)?.focus());

function ReadOnlyContent({ content }: { content: Content }) {
  const positions = new Map(
    content.groups.flatMap((g) => g.items).map((item, index) => [item.id, index + 1]),
  );
  return (
    <>
      <Alert tone="success">{fr.editor.readOnly}</Alert>
      {content.groups.map((group) => (
        <section key={group.id} className={styles.panel} aria-label={group.name}>
          <h2>{group.name}</h2>
          {group.items.map((item) => {
            const position = positions.get(item.id);
            return (
              <div key={item.id} className={styles.readItem}>
                <span className={styles.toolbarStatus}>{position}</span>
                <strong>{item.short_name}</strong>
                <span>{item.statement}</span>
              </div>
            );
          })}
        </section>
      ))}
    </>
  );
}

function Editor({ content, onSaved }: { content: Content; onSaved: (c: Content) => void }) {
  const { evaluation } = useEvaluation();
  const api = useApi();
  const versionId = content.version.id;
  const [draft, setDraft] = useState<Draft>(() => fromContent(content.groups));
  const [labels, setLabels] = useState<Labels>(content.color_labels);
  const [saved, setSaved] = useState(() => snapshot(fromContent(content.groups), labels));
  const [errors, setErrors] = useState<DraftError[]>([]);
  const [message, setMessage] = useState<Message | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragKey, setDragKey] = useState<string | null>(null);
  const [dropKey, setDropKey] = useState<string | null>(null);
  const [importMode, setImportMode] = useState<"replace" | "append">("replace");
  const [file, setFile] = useState<File | null>(null);
  const messageRef = useRef<HTMLDivElement>(null);
  const dirty = snapshot(draft, labels) !== saved;

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function show(next: Message) {
    setMessage(next);
    requestAnimationFrame(() => messageRef.current?.focus());
  }

  function errorFor(key: string, field: DraftError["field"]) {
    return errors.find((e) => e.key === key && e.field === field)?.message;
  }

  function accept(next: Content, text: string) {
    const nextDraft = fromContent(next.groups);
    setDraft(nextDraft);
    setLabels(next.color_labels);
    setSaved(snapshot(nextDraft, next.color_labels));
    setErrors([]);
    onSaved(next);
    show({ tone: "success", text });
  }

  function fail(reason: unknown) {
    const code = reason instanceof ApiError ? reason.code : "";
    show({ tone: "danger", text: messageOf(reason), reload: code === "CONTENT_CONFLICT" });
    if (code === "CONTENT_LOCKED")
      onSaved({ ...content, version: { ...content.version, editable: false } });
  }

  async function save() {
    const found = validate(draft);
    setErrors(found);
    const first = found[0];
    if (first) {
      focusSoon(`${first.field}-${first.key}`);
      return;
    }
    setBusy(true);
    try {
      const next = await call(
        api.PUT("/api/versions/{version_id}/content", {
          params: { path: { version_id: versionId } },
          body: {
            revision: content.version.revision,
            groups: toPayload(draft),
            color_labels: labels,
          },
        }),
      );
      accept(next, fr.editor.saved);
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  }

  async function importFile() {
    if (!file) return;
    setBusy(true);
    try {
      const next = await call(
        api.POST("/api/versions/{version_id}/items/import", {
          params: { path: { version_id: versionId } },
          body: { revision: content.version.revision, csv: await readText(file), mode: importMode },
        }),
      );
      const count = next.groups.reduce((total, group) => total + group.items.length, 0);
      accept(next, fr.editor.csvImported(count));
    } catch (reason) {
      fail(reason);
    } finally {
      setBusy(false);
    }
  }

  function add(groupKey: string) {
    const result = addItem(draft, groupKey);
    setDraft(result.draft);
    focusSoon(`short_name-${result.key}`);
  }

  const positions = new Map(
    draft.flatMap((g) => g.items).map((item, index) => [item.key, index + 1]),
  );
  return (
    <>
      <div className={styles.toolbar}>
        <span className={styles.toolbarStatus}>
          {fr.editor.count(itemCount(draft))}
          {dirty && <span className={styles.dirty}> · {fr.editor.unsaved}</span>}
        </span>
        <Button disabled={busy || !dirty} onClick={() => void save()}>
          {busy ? fr.editor.saving : fr.editor.save}
        </Button>
      </div>
      <p className={styles.toolbarStatus}>{fr.editor.fieldsHint}</p>
      {message && (
        <Alert tone={message.tone} ref={messageRef}>
          {message.text}{" "}
          {message.reload && (
            <Button variant="secondary" onClick={() => window.location.reload()}>
              {fr.editor.reload}
            </Button>
          )}
        </Alert>
      )}

      {draft.map((group, groupIndex) => (
        <section
          key={group.key}
          className={styles.group}
          aria-label={group.name || fr.editor.group}
        >
          <div className={styles.groupHead}>
            <Field
              id={`name-${group.key}`}
              label={fr.editor.groupName}
              value={group.name}
              maxLength={200}
              error={errorFor(group.key, "name")}
              onChange={(e) => setDraft(renameGroup(draft, group.key, e.target.value))}
            />
            <div className={styles.actions}>
              <Button
                variant="quiet"
                aria-label={`${fr.editor.moveUp} : ${group.name}`}
                disabled={groupIndex === 0}
                onClick={() => setDraft(moveGroup(draft, group.key, -1))}
              >
                ↑
              </Button>
              <Button
                variant="quiet"
                aria-label={`${fr.editor.moveDown} : ${group.name}`}
                disabled={groupIndex === draft.length - 1}
                onClick={() => setDraft(moveGroup(draft, group.key, 1))}
              >
                ↓
              </Button>
              <Button variant="quiet" onClick={() => setDraft(removeGroup(draft, group.key))}>
                {fr.editor.deleteGroup}
              </Button>
            </div>
          </div>
          {group.items.length === 0 && (
            <p className={styles.toolbarStatus}>{fr.editor.emptyGroup}</p>
          )}
          <ol className={styles.items}>
            {group.items.map((item) => {
              const position = positions.get(item.key) ?? 0;
              const label = fr.editor.itemLabel(position);
              return (
                <li
                  key={item.key}
                  className={styles.item}
                  data-dragging={dragKey === item.key}
                  data-drop={dropKey === item.key && dragKey !== item.key}
                  onDragOver={(event) => {
                    if (!dragKey) return;
                    event.preventDefault();
                    setDropKey(item.key);
                  }}
                  onDrop={(event) => {
                    event.preventDefault();
                    if (dragKey) setDraft(moveItemBefore(draft, dragKey, item.key));
                    setDragKey(null);
                    setDropKey(null);
                  }}
                >
                  <span
                    className={styles.handle}
                    draggable
                    aria-hidden="true"
                    onDragStart={(event) => {
                      event.dataTransfer.effectAllowed = "move";
                      setDragKey(item.key);
                    }}
                    onDragEnd={() => {
                      setDragKey(null);
                      setDropKey(null);
                    }}
                  >
                    {position}
                  </span>
                  <fieldset className={uiStyles.fieldset}>
                    <legend className={uiStyles.visuallyHidden}>{label}</legend>
                    <div className={styles.itemFields}>
                      <Field
                        id={`short_name-${item.key}`}
                        label={fr.editor.shortName}
                        value={item.short_name}
                        maxLength={50}
                        error={errorFor(item.key, "short_name")}
                        onChange={(e) =>
                          setDraft(updateItem(draft, item.key, { short_name: e.target.value }))
                        }
                      />
                      <TextAreaField
                        id={`statement-${item.key}`}
                        label={fr.editor.statement}
                        value={item.statement}
                        maxLength={2000}
                        rows={2}
                        error={errorFor(item.key, "statement")}
                        onChange={(e) =>
                          setDraft(updateItem(draft, item.key, { statement: e.target.value }))
                        }
                      />
                    </div>
                  </fieldset>
                  <div className={styles.itemActions}>
                    <Button
                      variant="quiet"
                      aria-label={`${fr.editor.moveUp} : ${label}`}
                      onClick={() => setDraft(moveItem(draft, item.key, -1))}
                    >
                      ↑ {fr.editor.moveUp}
                    </Button>
                    <Button
                      variant="quiet"
                      aria-label={`${fr.editor.moveDown} : ${label}`}
                      onClick={() => setDraft(moveItem(draft, item.key, 1))}
                    >
                      ↓ {fr.editor.moveDown}
                    </Button>
                    {draft.length > 1 && (
                      <select
                        className={uiStyles.select}
                        aria-label={`${fr.editor.moveTo} : ${label}`}
                        value={group.key}
                        onChange={(e) => setDraft(moveItemToGroup(draft, item.key, e.target.value))}
                      >
                        {draft.map((target) => (
                          <option key={target.key} value={target.key}>
                            {target.name || fr.editor.group}
                          </option>
                        ))}
                      </select>
                    )}
                    <Button
                      variant="quiet"
                      aria-label={`${fr.editor.deleteItem} : ${label}`}
                      onClick={() => setDraft(removeItem(draft, item.key))}
                    >
                      {fr.editor.deleteItem}
                    </Button>
                  </div>
                </li>
              );
            })}
          </ol>
          <div>
            <Button variant="secondary" onClick={() => add(group.key)}>
              + {fr.editor.addItem}
            </Button>
          </div>
        </section>
      ))}
      <div>
        <Button
          variant="secondary"
          onClick={() => {
            const next = addGroup(draft, fr.editor.newGroup);
            setDraft(next);
            const last = next[next.length - 1];
            if (last) focusSoon(`name-${last.key}`);
          }}
        >
          + {fr.editor.addGroup}
        </Button>
      </div>

      {evaluation.vote_preset === "custom" && (
        <section className={styles.panel} aria-labelledby="labels-title">
          <h2 id="labels-title">{fr.editor.labels}</h2>
          <p className={styles.toolbarStatus}>{fr.editor.labelsHint}</p>
          <div className={styles.labels}>
            {scale.map((color) => (
              <Field
                key={color.key}
                label={`${color.symbol} — ${color.labels.agreement}`}
                value={labels[color.key] ?? ""}
                placeholder={color.labels.agreement}
                maxLength={100}
                onChange={(e) => setLabels({ ...labels, [color.key]: e.target.value })}
              />
            ))}
          </div>
        </section>
      )}

      <section className={styles.panel} aria-labelledby="csv-title">
        <h2 id="csv-title">{fr.editor.csv}</h2>
        <p className={styles.toolbarStatus}>{fr.editor.csvHint}</p>
        <div>
          <a href={`/api/versions/${versionId}/items.csv`} download>
            {fr.editor.csvExport}
          </a>
        </div>
        <div className={uiStyles.field}>
          <label className={uiStyles.label} htmlFor="csv-file">
            {fr.editor.csvFile}
          </label>
          <input
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <RadioGroup
          legend={fr.editor.csvMode}
          name="import-mode"
          value={importMode}
          options={[
            { value: "replace", label: fr.editor.csvReplace },
            { value: "append", label: fr.editor.csvAppend },
          ]}
          onChange={setImportMode}
        />
        {dirty && <p className={styles.dirty}>{fr.editor.csvSaveFirst}</p>}
        <div>
          <Button
            variant="secondary"
            disabled={busy || dirty || !file}
            onClick={() => void importFile()}
          >
            {busy ? fr.editor.csvImporting : fr.editor.csvImport}
          </Button>
        </div>
      </section>
    </>
  );
}

export function ItemsEditorPage() {
  const { evaluation } = useEvaluation();
  const api = useApi();
  const [params, setParams] = useSearchParams();
  const fallback = currentVersion(evaluation.versions);
  const versionId = params.get("version") ?? fallback?.id ?? "";
  const [content, setContent] = useState<Content | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!versionId) return;
    let active = true;
    void call(
      api.GET("/api/versions/{version_id}", { params: { path: { version_id: versionId } } }),
    ).then(
      (data) => {
        if (active) setContent(data);
      },
      (reason: unknown) => {
        if (active) setError(messageOf(reason));
      },
    );
    return () => {
      active = false;
    };
  }, [api, versionId]);

  const options = useMemo(
    () =>
      evaluation.versions.map((v) => ({ id: v.id, text: `${v.label} — ${fr.statuses[v.status]}` })),
    [evaluation.versions],
  );

  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!content || content.version.id !== versionId) return <Spinner />;
  return (
    <>
      <div className={styles.actions}>
        {options.length > 1 ? (
          <label className={styles.actions}>
            <span className={uiStyles.label}>{fr.editor.version}</span>
            <select
              className={uiStyles.select}
              value={versionId}
              onChange={(e) => setParams({ version: e.target.value })}
            >
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.text}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <span className={uiStyles.label}>
            {fr.editor.version} {content.version.label}
          </span>
        )}
        <StatusBadge status={content.version.status} />
      </div>
      {content.version.editable ? (
        <Editor key={content.version.id} content={content} onSaved={setContent} />
      ) : (
        <ReadOnlyContent content={content} />
      )}
    </>
  );
}
