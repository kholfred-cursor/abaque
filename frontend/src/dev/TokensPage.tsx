import { flattenTokens } from "../shared/design/tokens";
import { scale } from "../shared/design/scale";
import { scaleClass } from "../shared/design/scaleClass";
import { useDocumentTitle } from "../shared/hooks/useDocumentTitle";
import { fr } from "../shared/i18n/fr";
import styles from "../admin/pages.module.css";

/** Development-only reference of the design tokens and the scale (route absent in builds). */
export function TokensPage() {
  useDocumentTitle(fr.titles.tokens);
  return (
    <>
      <h1>{fr.titles.tokens}</h1>
      <ul className={styles.list}>
        {scale.map((color) => (
          <li key={color.key} className={`${styles.row} ${scaleClass(color.key)}`}>
            <strong>{color.symbol}</strong> {color.labels.agreement} ({color.hex})
          </li>
        ))}
      </ul>
      <table>
        <tbody>
          {Object.entries(flattenTokens()).map(([name, value]) => (
            <tr key={name}>
              <th scope="row">{name}</th>
              <td>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
