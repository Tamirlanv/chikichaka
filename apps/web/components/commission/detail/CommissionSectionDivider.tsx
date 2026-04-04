/** Horizontal rule matching candidate-side separators: #E1E1E1, vertical margin configurable (default 56px). */
export function CommissionSectionDivider({ marginY = 56 }: { marginY?: number }) {
  return (
    <div
      role="separator"
      style={{
        height: 1,
        background: "#E1E1E1",
        margin: `${marginY}px 0`,
        border: "none",
        width: "100%",
      }}
    />
  );
}
