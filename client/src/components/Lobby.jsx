import React from "react";

export default function Lobby({ players = [], playerCount = 0, me, gameStarted = false, onVote = () => {} }) {
  return (
    <aside className="lobby">
      <h3>Lobby</h3>
      <div className="player-count">Players: {playerCount}</div>
      <ul className="player-list">
        {players.map((p) => (
          <li key={p.id} className={p.name === me ? "me" : ""}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <strong style={{ fontSize: 14 }}>{p.name}{p.name === me ? " (you)" : ""}</strong>
                <div style={{ fontSize: 12, color: "#9aa0a6" }}>{p.alive ? "alive" : "eliminated"}</div>
              </div>
              {gameStarted && p.alive && p.name !== me ? (
                <button onClick={() => onVote(p.id)} style={{ padding: "6px 8px", borderRadius: "8px", background: "rgba(255,255,255,0.04)", border: "none", cursor: "pointer", fontSize: 12 }}>
                  Vote
                </button>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
