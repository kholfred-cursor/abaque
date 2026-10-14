import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useParams } from "react-router";
import { useApi } from "../shared/api/ApiContext";
import { call } from "../shared/api/call";
import { ApiError } from "../shared/api/errors";
import type { components } from "../shared/api/schema";
import { scale, type ScaleKey } from "../shared/design/scale";
import { scaleClass } from "../shared/design/scaleClass";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { fr } from "../shared/i18n/fr";
import { Alert } from "../shared/ui/Alert";
import { Button } from "../shared/ui/Button";
import { TextAreaField } from "../shared/ui/Field";
import { ParticipantLayout } from "../shared/ui/Layout";
import { Spinner } from "../shared/ui/Spinner";
import uiStyles from "../shared/ui/ui.module.css";
import { clearDraft, loadDraft, saveDraft, type Answer } from "./draft";
import { Markdown } from "./Markdown";
import styles from "./vote.module.css";

type PublicVersion = components["schemas"]["PublicVersionResponse"];
type PublicItem = components["schemas"]["PublicItem"];
type Answers = Record<string, Answer>;
type Phase = "intro" | "vote" | "review" | "done" | "refused" | "already";

const SYMBOL = Object.fromEntries(scale.map((c) => [c.key, c.symbol])) as Record<ScaleKey, string>;
const COMMENT_MAX = 2000;

/** The voter's own row of the abaque: one cell per statement, in its chosen colour. */
function Progress({
  items,
  answers,
  current,
}: {
  items: PublicItem[];
  answers: Answers;
  current: Set<string>;
}) {
  const answered = items.filter((item) => answers[item.id]).length;
  return (
    <div
      className={styles.progress}
      role="progressbar"
      aria-label={fr.vote.progressLabel}
      aria-valuemin={0}
      aria-valuemax={items.length}
      aria-valuenow={answered}
      aria-valuetext={fr.vote.progress(answered, items.length)}
    >
      <div className={styles.cells} aria-hidden="true">
        {items.map((item) => {
          const color = answers[item.id]?.color;
          return (
            <span
              key={item.id}
              className={[
                styles.cell,
                color ? scaleClass(color) : styles.empty,
                current.has(item.id) ? styles.current : "",
              ].join(" ")}
            />
          );
        })}
      </div>
      <div className={styles.progressText}>
        <span>{fr.vote.progress(answered, items.length)}</span>
      </div>
    </div>
  );
}

function ItemCard({
  item,
  position,
  total,
  labels,
  answer,
  onChange,
}: {
  item: PublicItem;
  position: number;
  total: number;
  labels: Record<string, string>;
  answer: Answer | undefined;
  onChange: (answer: Answer) => void;
}) {
  const [showComment, setShowComment] = useState(Boolean(answer?.comment));
  const statementId = useId();
  return (
    <article className={styles.item} aria-labelledby={statementId}>
      <p className={styles.itemNumber}>{fr.vote.itemOf(position, total)}</p>
      <p id={statementId} className={styles.statement}>
        {item.statement}
      </p>
      <fieldset className={styles.choices}>
        <legend className={uiStyles.visuallyHidden}>
          {fr.vote.choice} : {item.statement}
        </legend>
        {scale.map((color) => {
          const selected = answer?.color === color.key;
          return (
            <label
              key={color.key}
              className={`${styles.choice} ${selected ? scaleClass(color.key) : ""}`}
              data-selected={selected}
            >
              <input
                type="radio"
                name={`item-${item.id}`}
                value={color.key}
                checked={selected}
                onChange={() => onChange({ color: color.key, comment: answer?.comment ?? "" })}
              />
              <span className={`${styles.swatch} ${scaleClass(color.key)}`} aria-hidden="true">
                {color.symbol}
              </span>
              <span className={styles.choiceLabel}>{labels[color.key]}</span>
              <span className={styles.check} aria-hidden="true">
                {selected ? "✓" : ""}
              </span>
            </label>
          );
        })}
      </fieldset>
      {answer && (
        <>
          <Button
            variant="quiet"
            className={styles.commentToggle}
            aria-expanded={showComment}
            onClick={() => setShowComment(!showComment)}
          >
            {showComment ? fr.vote.hideComment : fr.vote.addComment}
          </Button>
          {showComment && (
            <div className={styles.commentBlock}>
              <TextAreaField
                label={fr.vote.comment}
                hint={fr.vote.commentWarning}
                value={answer.comment}
                maxLength={COMMENT_MAX}
                rows={3}
                onChange={(e) => onChange({ ...answer, comment: e.target.value })}
              />
            </div>
          )}
        </>
      )}
    </article>
  );
}

function AnswerList({
  page,
  answers,
  labels,
}: {
  page: PublicVersion;
  answers: Answers;
  labels: Record<string, string>;
}) {
  return (
    <section aria-labelledby="answers-title" className={styles.texts}>
      <h2 id="answers-title">{fr.vote.yourAnswers}</h2>
      <ul className={styles.answers}>
        {page.groups
          .flatMap((g) => g.items)
          .map((item) => {
            const answer = answers[item.id];
            return (
              <li key={item.id}>
                <span
                  className={`${styles.answerSwatch} ${answer ? scaleClass(answer.color) : styles.empty}`}
                  aria-hidden="true"
                >
                  {answer ? SYMBOL[answer.color] : ""}
                </span>
                <span>
                  {item.statement}
                  <br />
                  <strong>{answer ? labels[answer.color] : fr.vote.noAnswer}</strong>
                  {answer?.comment && (
                    <span className={styles.answerComment}> — « {answer.comment} »</span>
                  )}
                </span>
              </li>
            );
          })}
      </ul>
    </section>
  );
}

function Voting({ page, slug }: { page: PublicVersion; slug: string }) {
  const api = useApi();
  const versionId = page.version_id ?? "";
  const [initial] = useState(() => loadDraft(versionId));
  const [answers, setAnswers] = useState<Answers>(initial?.answers ?? {});
  const [group, setGroup] = useState(() =>
    Math.min(initial?.group ?? 0, Math.max(page.groups.length - 1, 0)),
  );
  const [phase, setPhase] = useState<Phase>(page.already_voted ? "already" : "intro");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const alertRef = useRef<HTMLDivElement>(null);
  const items = useMemo(() => page.groups.flatMap((g) => g.items), [page.groups]);
  const labels = useMemo(
    () => Object.fromEntries(page.scale.map((s) => [s.key, s.label])),
    [page.scale],
  );
  const positions = useMemo(() => new Map(items.map((item, n) => [item.id, n + 1])), [items]);
  const answered = items.filter((item) => answers[item.id]).length;
  const hasDraft = initial !== null && Object.keys(initial.answers).length > 0;

  useEffect(() => {
    if (phase === "vote" || phase === "review") saveDraft(versionId, { answers, group });
  }, [answers, group, phase, versionId]);

  function goTo(next: Phase, nextGroup = group) {
    setPhase(next);
    setGroup(nextGroup);
    setError(null);
    window.scrollTo?.(0, 0);
    requestAnimationFrame(() => headingRef.current?.focus());
  }

  async function send() {
    if (answered === 0) {
      setError(fr.vote.nothingYet);
      return;
    }
    setSending(true);
    setError(null);
    try {
      await call(
        api.POST("/api/public/v/{slug}/ballots", {
          params: { path: { slug } },
          body: {
            version_id: versionId,
            votes: items
              .filter((item) => answers[item.id])
              .map((item) => {
                const answer = answers[item.id] as Answer;
                const comment = answer.comment.trim();
                return {
                  item_id: item.id,
                  color_key: answer.color,
                  ...(comment ? { comment } : {}),
                };
              }),
          },
        }),
      );
      clearDraft(versionId);
      goTo("done");
    } catch (reason) {
      const code = reason instanceof ApiError ? reason.code : "";
      const message = reason instanceof ApiError ? reason.message : fr.errors.GENERIC;
      if (code === "VERSION_CLOSED") {
        setPhase("refused");
        setError(message);
      } else if (code === "ALREADY_VOTED") {
        clearDraft(versionId);
        setPhase("already");
      } else {
        setError(message);
        requestAnimationFrame(() => alertRef.current?.focus());
      }
    } finally {
      setSending(false);
    }
  }

  if (phase === "already") {
    return (
      <div className={styles.page}>
        <h1>{fr.vote.alreadyTitle}</h1>
        <p>{fr.vote.alreadyHint}</p>
      </div>
    );
  }

  if (phase === "done") {
    return (
      <div className={`${styles.page} ${styles.done}`}>
        <span className={styles.doneMark} aria-hidden="true">
          ✓
        </span>
        <h1 ref={headingRef} tabIndex={-1}>
          {fr.vote.doneTitle}
        </h1>
        {page.outro_md && (
          <div className={styles.prose}>
            <Markdown text={page.outro_md} />
          </div>
        )}
      </div>
    );
  }

  if (phase === "refused") {
    return (
      <div className={styles.page}>
        <Alert tone="danger">{error ?? fr.errors.VERSION_CLOSED}</Alert>
        <p>{fr.vote.keptDraft}</p>
        <AnswerList page={page} answers={answers} labels={labels} />
      </div>
    );
  }

  if (phase === "intro") {
    return (
      <div className={styles.page}>
        <p className={styles.eyebrowTitle}>{fr.app.name}</p>
        <h1>{page.title}</h1>
        {page.intro_md && (
          <div className={styles.prose}>
            <Markdown text={page.intro_md} />
          </div>
        )}
        {page.show_vote_example && (
          <section className={styles.texts} aria-labelledby="scale-title">
            <h2 id="scale-title">{fr.vote.scaleTitle}</h2>
            <p>{fr.vote.scaleHint}</p>
            <ul className={styles.answers}>
              {scale.map((color) => (
                <li key={color.key}>
                  <span
                    className={`${styles.answerSwatch} ${scaleClass(color.key)}`}
                    aria-hidden="true"
                  >
                    {color.symbol}
                  </span>
                  <span>{labels[color.key]}</span>
                </li>
              ))}
            </ul>
          </section>
        )}
        <p className={styles.guarantee}>{fr.vote.guarantee}</p>
        {hasDraft && <Alert tone="notice">{fr.vote.resumeHint}</Alert>}
        <div className={styles.nav}>
          <Button onClick={() => goTo("vote")}>{hasDraft ? fr.vote.resume : fr.vote.start}</Button>
        </div>
      </div>
    );
  }

  const currentGroup = page.groups[group];
  const current = new Set(phase === "vote" ? (currentGroup?.items.map((i) => i.id) ?? []) : []);
  const isLast = group >= page.groups.length - 1;

  return (
    <div className={styles.page}>
      <Progress items={items} answers={answers} current={current} />
      {phase === "review" ? (
        <section className={styles.texts} aria-labelledby="review-title">
          <h1 id="review-title" ref={headingRef} tabIndex={-1}>
            {fr.vote.reviewTitle}
          </h1>
          <p className={styles.lead}>{fr.vote.reviewAnswered(answered, items.length)}</p>
          {answered < items.length && (
            <>
              <p>{fr.vote.reviewMissing}</p>
              <ul className={styles.missing}>
                {page.groups.flatMap((g, groupIndex) =>
                  g.items
                    .filter((item) => !answers[item.id])
                    .map((item) => (
                      <li key={item.id}>
                        <span>{item.statement}</span>
                        <Button
                          variant="quiet"
                          aria-label={`${fr.vote.goTo} : ${item.statement}`}
                          onClick={() => goTo("vote", groupIndex)}
                        >
                          {fr.vote.goTo}
                        </Button>
                      </li>
                    )),
                )}
              </ul>
            </>
          )}
          <p className={styles.guarantee}>{fr.vote.reviewFinal}</p>
          {error && (
            <Alert tone="danger" ref={alertRef}>
              {error}
            </Alert>
          )}
          <div className={styles.nav}>
            <Button variant="secondary" onClick={() => goTo("vote", page.groups.length - 1)}>
              {fr.vote.backToVote}
            </Button>
            <Button disabled={sending} onClick={() => void send()}>
              {sending ? fr.vote.sending : fr.vote.send}
            </Button>
          </div>
        </section>
      ) : (
        currentGroup && (
          <section className={styles.texts} aria-labelledby="group-title">
            <p className={styles.eyebrowTitle}>
              {page.groups.length > 1 ? fr.vote.groupOf(group + 1, page.groups.length) : page.title}
            </p>
            <h1 id="group-title" ref={headingRef} tabIndex={-1}>
              {currentGroup.name}
            </h1>
            {currentGroup.items.map((item) => (
              <ItemCard
                key={item.id}
                item={item}
                position={positions.get(item.id) ?? 0}
                total={items.length}
                labels={labels}
                answer={answers[item.id]}
                onChange={(answer) => setAnswers({ ...answers, [item.id]: answer })}
              />
            ))}
            <div className={styles.nav}>
              {group > 0 && (
                <Button variant="secondary" onClick={() => goTo("vote", group - 1)}>
                  {fr.vote.previous}
                </Button>
              )}
              <Button onClick={() => (isLast ? goTo("review") : goTo("vote", group + 1))}>
                {isLast ? fr.vote.review : fr.vote.next}
              </Button>
            </div>
          </section>
        )
      )}
    </div>
  );
}

export function VotePage() {
  const { slug = "" } = useParams();
  const api = useApi();
  const [page, setPage] = useState<PublicVersion | null>(null);
  const [error, setError] = useState<string | null>(null);
  useDocumentTitle(page?.title ?? fr.titles.vote);

  useEffect(() => {
    let active = true;
    void call(api.GET("/api/public/v/{slug}", { params: { path: { slug } } })).then(
      (data) => {
        if (active) setPage(data);
      },
      (reason: unknown) => {
        if (!active) return;
        const notFound = reason instanceof ApiError && reason.status === 404;
        setError(
          notFound
            ? fr.vote.unknown
            : reason instanceof ApiError
              ? reason.message
              : fr.errors.GENERIC,
        );
      },
    );
    return () => {
      active = false;
    };
  }, [api, slug]);

  let body;
  if (error) body = <Alert tone="danger">{error}</Alert>;
  else if (!page) body = <Spinner />;
  else if (page.status === "closed") {
    body = (
      <div className={styles.page}>
        <h1>{fr.vote.closedTitle}</h1>
        <p>{fr.vote.closedHint}</p>
      </div>
    );
  } else body = <Voting key={page.version_id} page={page} slug={slug} />;

  return <ParticipantLayout>{body}</ParticipantLayout>;
}
