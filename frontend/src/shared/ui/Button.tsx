import type { ButtonHTMLAttributes } from "react";
import styles from "./ui.module.css";

type Variant = "primary" | "secondary" | "quiet";

export function Button({
  variant = "primary",
  className,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const variantClass = variant === "primary" ? "" : styles[variant];
  return (
    <button
      type={type}
      className={[styles.button, variantClass, className].filter(Boolean).join(" ")}
      {...props}
    />
  );
}
