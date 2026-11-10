export default function Loading() {
  return (
    <div aria-busy="true" aria-label="Загрузка" className="stack" style={{ paddingTop: 56 }}>
      <div className="skel" style={{ height: 40, width: "60%" }} />
      <div className="skel" style={{ height: 130 }} />
      <div className="skel" style={{ height: 110 }} />
      <div className="skel" style={{ height: 160 }} />
    </div>
  );
}
