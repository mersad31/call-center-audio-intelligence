# main.py
import argparse
import json
from pathlib import Path

import uvicorn

from .preprocessing import preprocess_conversation
from .rules import validate_input, validate_emotional_content
from .sentiment_model import SentimentModel
from .scoring import score_messages
from .request_id import generate_new_id, set_request_id

def read_input(input_arg: str) -> str:
    p = Path(input_arg)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return input_arg


def cli_analyze(text: str) -> dict:
    cli_id = generate_new_id()
    set_request_id(cli_id)

    messages = preprocess_conversation(text)

    err = validate_input(text, messages)
    if err:
        if isinstance(err, dict) and "error" in err:
            err["request_id"] = cli_id
        return err

    model = SentimentModel()
    labels = model.predict(messages)

    err = validate_emotional_content(messages, labels)
    if err:
        if isinstance(err, dict) and "error" in err:
            err["request_id"] = cli_id
        return err

    sentiment, detail = score_messages(messages)
    
    return {
        "request_id": cli_id,
        "sentiment": sentiment,
        "detail": detail,
    }


def main():
    parser = argparse.ArgumentParser(description="Persian Sentiment Analyzer")
    parser.add_argument("--input", type=str, help="Conversation text or file path")
    parser.add_argument("--serve", action="store_true", help="Run FastAPI server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8007)

    args = parser.parse_args()

    if args.serve:
        uvicorn.run("app.api:app", host=args.host, port=args.port, reload=False)
        return

    if not args.input:
        cli_id = generate_new_id()
        print(json.dumps({
            "request_id": cli_id,
            "error": {"code": "E01", "message": "Empty input."}
        }, ensure_ascii=False))
        return

    text = read_input(args.input)
    result = cli_analyze(text)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()