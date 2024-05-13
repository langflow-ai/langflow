function AnnotationNode({ data }) {
  return (
    <div className="relative">
      <div style={{ padding: 10, display: "flex" }}>
        <div style={{ marginRight: 4 }}>{data.level}.</div>
        <div>{data.label}</div>
      </div>
      {data.arrowStyle && (
        <div
          className="arrow absolute -bottom-2 -right-2"
          style={data.arrowStyle}
        >
          ⤹
        </div>
      )}
    </div>
  );
}

export default AnnotationNode;
