import {
  forwardRef,
  useId,
  useState,
  type InputHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { fr } from "../i18n/fr";
import styles from "./ui.module.css";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  hint?: string | undefined;
  error?: string | undefined;
}

/** Label, input, hint and error wired together (aria-describedby, aria-invalid). */
export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  { label, hint, error, id, ...props },
  ref,
) {
  const generated = useId();
  const inputId = id ?? generated;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      {hint && (
        <span id={hintId} className={styles.hint}>
          {hint}
        </span>
      )}
      <input
        ref={ref}
        id={inputId}
        className={styles.input}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
      />
      {error && (
        <span id={errorId} className={styles.error}>
          {error}
        </span>
      )}
    </div>
  );
});

interface PasswordFieldProps extends Omit<FieldProps, "type"> {
  autoComplete: "current-password" | "new-password";
}

/** Password input with a show/hide toggle; new passwords display the policy rule. */
export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
  function PasswordField({ label, hint, error, id, autoComplete, ...props }, ref) {
    const [visible, setVisible] = useState(false);
    const generated = useId();
    const inputId = id ?? generated;
    const ruleId = autoComplete === "new-password" ? `${inputId}-rule` : undefined;
    const errorId = error ? `${inputId}-error` : undefined;
    const describedBy = [errorId, ruleId].filter(Boolean).join(" ") || undefined;
    return (
      <div className={styles.field}>
        <label className={styles.label} htmlFor={inputId}>
          {label}
        </label>
        {ruleId && (
          <span id={ruleId} className={styles.hint}>
            {hint ?? fr.fields.passwordRule}
          </span>
        )}
        <div className={styles.passwordRow}>
          <input
            ref={ref}
            id={inputId}
            type={visible ? "text" : "password"}
            className={styles.input}
            autoComplete={autoComplete}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            {...props}
          />
          <button
            type="button"
            className={`${styles.button} ${styles.secondary} ${styles.toggle}`}
            aria-label={fr.fields.showPasswordLabel}
            aria-pressed={visible}
            onClick={() => setVisible((v) => !v)}
          >
            {fr.fields.showPassword}
          </button>
        </div>
        {error && (
          <span id={errorId} className={styles.error}>
            {error}
          </span>
        )}
      </div>
    );
  },
);

interface TextAreaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string | undefined;
  error?: string | undefined;
}

/** Multi-line counterpart of Field, with the same label/hint/error wiring. */
export function TextAreaField({ label, hint, error, id, ...props }: TextAreaFieldProps) {
  const generated = useId();
  const inputId = id ?? generated;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={inputId}>
        {label}
      </label>
      {hint && (
        <span id={hintId} className={styles.hint}>
          {hint}
        </span>
      )}
      <textarea
        id={inputId}
        className={`${styles.input} ${styles.textarea}`}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        {...props}
      />
      {error && (
        <span id={errorId} className={styles.error}>
          {error}
        </span>
      )}
    </div>
  );
}

/** A labelled choice among a few options (radio buttons in a fieldset). */
export function RadioGroup<T extends string>({
  legend,
  name,
  value,
  options,
  onChange,
  disabled,
}: {
  legend: string;
  name: string;
  value: T;
  options: readonly { value: T; label: string; hint?: string }[];
  onChange: (value: T) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset className={styles.fieldset} disabled={disabled}>
      <legend className={styles.label}>{legend}</legend>
      {options.map((option) => (
        <label key={option.value} className={styles.choice}>
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={value === option.value}
            onChange={() => onChange(option.value)}
          />
          <span>
            {option.label}
            {option.hint && <span className={styles.hint}> — {option.hint}</span>}
          </span>
        </label>
      ))}
    </fieldset>
  );
}
