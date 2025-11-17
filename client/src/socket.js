import { io } from "socket.io-client";
const SERVER_URL = import.meta.env.VITE_SERVER_URL || "http://localhost:5050";
const socket = io(SERVER_URL, {
  autoConnect: true,
  transports: ["websocket", "polling"],
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 500,
});
export default socket;
