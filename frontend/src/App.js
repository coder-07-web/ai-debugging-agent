import Editor from "@monaco-editor/react";
import axios from "axios";
import { useState } from "react";

function App() {
  const [code, setCode] = useState("");
  const [fixedCode, setFixedCode] = useState("");
  const [result, setResult] = useState("");
  const [language, setLanguage] = useState("python");

  const handleDebug = async () => {
    try {
      const res = await axios.post(
        "http://127.0.0.1:8000/api/debug/",
        {
          code: code,
          language: language,
        }
      );

      setResult(res.data.full_response);
      setFixedCode(res.data.fixed_code);
    } catch (error) {
      console.error(error);
      alert("Backend error");
    }
  };

  return (
    <div
      style={{
        padding: "20px",
        color: "white",
        background: "#1e1e1e",
        minHeight: "100vh",
      }}
    >
      <h1>🚀 AI Debugging Agent</h1>

      {/* Language Selector */}
      <div style={{ marginBottom: "15px" }}>
        <label
          style={{
            marginRight: "10px",
            fontSize: "16px",
          }}
        >
          Select Language:
        </label>

        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          style={{
            padding: "8px",
            background: "#2d2d2d",
            color: "white",
            border: "1px solid #555",
            borderRadius: "5px",
          }}
        >
          <option value="python">Python</option>
          <option value="javascript">JavaScript</option>
          <option value="java">Java</option>
          <option value="cpp">C++</option>
          <option value="c">C</option>
          <option value="sql">SQL</option>
          <option value="html">HTML</option>
          <option value="css">CSS</option>
          <option value="typescript">TypeScript</option>
        </select>
      </div>

      {/* Code Editor */}
      <Editor
        height="300px"
        language={language}
        theme="vs-dark"
        value={code}
        onChange={(value) => setCode(value || "")}
      />

      <br />

      {/* Debug Button */}
      <button onClick={handleDebug}>
        Debug Code
      </button>

      {/* Apply Fix Button */}
      <button
        onClick={() => setCode(fixedCode)}
        disabled={!fixedCode}
        style={{ marginLeft: "10px" }}
      >
        Apply Fix
      </button>

      {/* Explanation */}
      <h3>Explanation:</h3>
      <pre>{result}</pre>

      {/* Fixed Code */}
      <h3>Fixed Code:</h3>
      <pre>{fixedCode}</pre>
    </div>
  );
}

export default App;