import { useState } from "react";

export default function App() {
  const [camUrl, setCamUrl] = useState(
    "https://via.placeholder.com/640x360?text=Camera"
  );
  const [test1, setTest1] = useState("test1");
  const [test2, setTest2] = useState("test2");

  const onSendEsp = () => {
    console.log("[UI] Send ESP clicked");
    // later: publish to esp/cmd
  };

  const onSendPi = () => {
    console.log("[UI] Send Pi clicked");
    // later: publish to pi/cmd
  };

  return (
    <div
      style={{
        fontFamily: "Inter, system-ui, Arial",
        padding: 16,
        maxWidth: 960,
        margin: "0 auto",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 16,
        }}
      >
        <h1 style={{ margin: 0 }}>Lake Buoy Dashboard</h1>
      </header>


      {/* Controls */}
      <section style={{ marginBottom: 16 }}>
        <h2 style={{ marginBottom: 8 }}>Controls</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            onClick={onSendEsp}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #ccc",
              cursor: "pointer",
            }}
            title="(no action yet)"
          >
            Send ESP
          </button>
          <button
            onClick={onSendPi}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #ccc",
              cursor: "pointer",
            }}
            title="(no action yet)"
          >
            Send Pi
          </button>
        </div>
      </section>

      {/* Read-only text boxes (placeholders for incoming data later) */}
      <section style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
          <label
            htmlFor="test1"
            style={{ fontSize: 12, color: "#666", marginBottom: 6, display: "block" }}
          >
            Test1 (from esp/test)
          </label>
          <input
            id="test1"
            value={test1}
            readOnly
            style={{
              width: "100%",
              padding: 10,
              borderRadius: 8,
              border: "1px solid #ccc",
              background: "#f9f9f9",
            }}
          />
        </div>

        <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
          <label
            htmlFor="test2"
            style={{ fontSize: 12, color: "#666", marginBottom: 6, display: "block" }}
          >
            Test2 (from pi/test)
          </label>
          <input
            id="test2"
            value={test2}
            readOnly
            style={{
              width: "100%",
              padding: 10,
              borderRadius: 8,
              border: "1px solid #ccc",
              background: "#f0f0f0",
            }}
          />
        </div>
      </section>
    </div>
  );
}
