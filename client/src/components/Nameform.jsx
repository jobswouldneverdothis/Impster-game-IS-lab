import React, { useState } from "react";

export default function NameForm({ onSubmit }) {
  const [value, setValue] = useState("");
  const submit = (e) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    onSubmit(trimmed);
  };
  return (
    <form className="name-form" onSubmit={submit}>
      <h2>Enter name to join</h2>
      <input value={value} onChange={(e) => setValue(e.target.value)} placeholder="Your name" maxLength={24} />
      <button type="submit">Join Game</button>
    </form>
  );
}
