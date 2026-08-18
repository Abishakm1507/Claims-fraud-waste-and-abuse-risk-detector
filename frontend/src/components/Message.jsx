import Answer from "./Answer.jsx";

/** One turn in the conversation. */
export default function Message({ message }) {
  const time = message.time || "";

  if (message.role === "user") {
    return (
      <div className="msg">
        <div className="avatar user" aria-hidden="true">You</div>
        <div className="msg-body">
          <div className="bubble-user">{message.text}</div>
          {time && <div className="stamp">{time}</div>}
        </div>
      </div>
    );
  }

  return (
    <div className="msg">
      <div className="avatar bot" aria-hidden="true">IA</div>
      <div className="msg-body">
        <Answer text={message.answer} isError={message.isError} />
        {time && <div className="stamp">{time}</div>}
      </div>
    </div>
  );
}
