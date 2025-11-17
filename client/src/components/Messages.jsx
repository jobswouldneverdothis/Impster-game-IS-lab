import React, { useState, useEffect, useRef } from "react";

export default function Messages({
  messages = [],
  onSend,
  role,
  word,
  cluesRevealed,
  revealedClues = {},
  submitClue,
  votingProgress = {},
  myName
}) {
  const [text, setText] = useState("");
  const [clueText, setClueText] = useState("");
  const listRef = useRef(null);

  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages.length, cluesRevealed]);

  const submit = (e) => {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  };

  const submitClueLocal = (e) => {
    e.preventDefault();
    const trimmed = clueText.trim();
    if (!trimmed) return;
    submitClue(trimmed);
    setClueText("");
  };

  return (
    <section className="messages">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <div>
          {role ? <strong style={{ marginRight: 12 }}>Role: {role}</strong> : null}
          {word ? <span>Word: <em>{word}</em></span> : null}
        </div>
        <div style={{ fontSize: 13, color: "#9aa0a6" }}>
          {votingProgress.votesCount ? (
            <span>{votingProgress.votesCount}/{votingProgress.aliveCount} voted</span>
          ) : (
            votingProgress.aliveCount ? <span>0/{votingProgress.aliveCount} voted</span> : <span></span>
          )}
        </div>
      </div>

      <div style={{ marginBottom: 8 }}>
        {!cluesRevealed && role ? (
          <form onSubmit={submitClueLocal} style={{ display: "flex", gap: 8 }}>
            <input placeholder="Submit one clue" value={clueText} onChange={(e) => setClueText(e.target.value)} />
            <button type="submit">Submit Clue</button>
          </form>
        ) : null}
      </div>

      <div className="messages-list" id="messagesList" ref={listRef}>
        {cluesRevealed && Object.keys(revealedClues).length > 0 ? (
          <div className="msg-system">
            📣 Clues:
            <div style={{ marginTop: 8 }}>
              {Object.entries(revealedClues).map(([n, c]) => (
                <div key={n} style={{ marginBottom: 6 }}>
                  <strong>{n}:</strong> {c}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {messages.map((m, idx) => {
          if (m.type === "system") {
            return <div key={idx} className="msg-system">— {m.text}</div>;
          }
          if (m.type === "chat") {
            return (
              <div key={idx} className="msg-chat">
                <span className="msg-from">{m.from}:</span>
                <span className="msg-text">{m.text}</span>
              </div>
            );
          }
          if (m.type === "vote") {
            return (
              <div key={idx} className="msg-system">🗳️ {m.text}</div>
            );
          }
          if (m.type === "vote_results") {
            return (
              <div key={idx} className="msg-system">
                🔔 {m.eliminatedName} was eliminated. Tally:
                <div style={{ fontSize: 13, marginTop: 6 }}>
                  {m.tally && Object.entries(m.tally).map(([name, count]) => (
                    <div key={name}>{name}: {count}</div>
                  ))}
                </div>
              </div>
            );
          }
          return <div key={idx} className="msg-system">{JSON.stringify(m)}</div>;
        })}
      </div>

      <form className="message-form" onSubmit={submit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={myName ? "Type a message and press Enter" : "Join to chat"}
          disabled={!myName}
        />
        <button type="submit" disabled={!myName}>Send</button>
      </form>
    </section>
  );
}
