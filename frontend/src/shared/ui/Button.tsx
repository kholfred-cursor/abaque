import type { ButtonHTMLAttributes, Ref } from "react";
import styles from "./ui.module.css";

type Variant = "primary" | "secondary" | "quiet";

/** React 19: ``ref`` is an ordinary prop (used to give focus back after a dialog). */
export function Button({
  variant = "primary",
  className,
  type = "button",
  ref,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; ref?: Ref<HTMLButtonElement> }) {
  const variantClass = variant === "primary" ? "" : styles[variant];
  return (
    <button
      ref={ref}
      type={type}
      className={[styles.button, variantClass, className].filter(Boolean).join(" ")}
      {...props}
    />
  );
}
