import Editor from "@monaco-editor/react";
import axios from "axios";
import { useState } from "react";

function App() {
  const [code, setCode] = useState("");
  const [fixedCode, setFixedCode] = useState("");
  const [result, setResult] = useState("");

  const handleDebug = async () => {
    try {
      const res = await axios.post("http://127.0.0.1:8000/api/debug/", {
        code: code,
      });

      setResult(res.data.full_response);
      setFixedCode(res.data.fixed_code);
    } catch (error) {
      console.error(error);
      alert("Backend error");
    }
  };

  return (
    <div style={{ padding: "20px", color: "white", background: "#1e1e1e", minHeight: "100vh" }}>
      <h1>🚀 AI Debugging Agent</h1>

      <Editor
        height="300px"
        defaultLanguage="python"
        theme="vs-dark"
        value={code}
        onChange={(value) => setCode(value)}
      />

      <br />

      <button onClick={handleDebug}>Debug Code</button>

      <button 
        onClick={() => setCode(fixedCode)} 
        disabled={!fixedCode}
        style={{ marginLeft: "10px" }}
      >
        Apply Fix
      </button>

      <h3>Explanation:</h3>
      <pre>{result}</pre>

      <h3>Fixed Code:</h3>
      <pre>{fixedCode}</pre>
    </div>
  );
}

export default App;