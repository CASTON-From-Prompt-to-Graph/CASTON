    train = np.asarray(train_embeddings, dtype=np.float64)
    val = np.asarray(val_embeddings, dtype=np.float64)
    if (train.ndim != 2 or val.ndim != 2 or train.shape[1] != val.shape[1]
            or not train.shape[0] or not val.shape[0] or not train.shape[1]):
        raise ValueError("Embeddings must be nonempty 2D arrays of matching dimension")
    if not np.isfinite(train).all() or not np.isfinite(val).all():
        raise ValueError("Embeddings must be finite")
    train_norm = np.linalg.norm(train, axis=1, keepdims=True)
    val_norm = np.linalg.norm(val, axis=1, keepdims=True)
    if (train_norm == 0).any() or (val_norm == 0).any():
        raise ValueError("Cosine similarity is undefined for a zero embedding")
    normalized_train = train / train_norm
    normalized_val = val / val_norm
    # Process one query at a time to avoid a full validation x training matrix.
    return [np.argsort(normalized_train @ query)[::-1][:k].tolist()
            for query in normalized_val]


def retrieve_neighbors(training, validation, model_name, top_k, batch_size):
    """Embed user inputs with AnglE/UAE; never embed assistant annotations."""
    if top_k == 0:
        return [[] for _ in validation]
    from angle_emb import AnglE

    encoder = AnglE.from_pretrained(model_name, pooling_strategy="cls")
    # No query prompt (e.g. Prompts.C), matching both original similarity scripts.
    import numpy as np

    def encode_batches(texts):
        batches = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start:start + batch_size]
            embeddings = np.asarray(encoder.encode(batch, to_numpy=True))
            if embeddings.ndim != 2 or embeddings.shape[0] != len(batch):
                raise ValueError("Encoder must return one vector per input text")
            batches.append(embeddings)
        return np.concatenate(batches, axis=0)

    train_embeddings = encode_batches([item[0] for item in training])
    val_embeddings = encode_batches(validation)
    return cosine_top_k(train_embeddings, val_embeddings, min(top_k, len(training)))


def save_neighbors(path, neighbors):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        for indices in neighbors:
            handle.write(json.dumps(indices) + "\n")


def run():
    parser = argparse.ArgumentParser(description=(
        f"Casting {TASK.upper()}: AnglE cosine retrieval followed by GPT ICL extraction."))
    parser.add_argument("--train", required=True, help="Training messages JSONL")
    if TASK == "ner":
        parser.add_argument("--val-dir", required=True, help="UTF-8 .txt inputs in natural filename order")
    else:
        parser.add_argument("--val", required=True, help="Validation messages JSONL")
    parser.add_argument("--top-k", type=int, default=16, help="Retrieved examples per input (default: 16)")
    parser.add_argument("--embedding-model", default="WhereIsAI/UAE-Large-V1",
                        help="AnglE model ID or local model directory")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--knn", type=Path, help="Optional existing neighbor JSONL; bypasses embedding retrieval and --top-k")
    parser.add_argument("--neighbors-output", type=Path, help="Optional neighbor JSONL export")
    parser.add_argument("--retrieve-only", action="store_true", help="Retrieve/export neighbors without calling OpenAI")
    parser.add_argument("--output", type=Path, default=Path(f"outputs/{TASK}_predictions.json"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--dry-run", action="store_true", help="Check data only; no model downloads, inference, or writes")
    args = parser.parse_args()
    if args.top_k < 0 or args.batch_size <= 0 or args.max_tokens <= 0:
        parser.error("--top-k must be nonnegative; --batch-size and --max-tokens must be positive")
    if args.retrieve_only and not args.neighbors_output:
        parser.error("--retrieve-only requires --neighbors-output")
    try:
        training, validation, neighbors = load_inputs(TASK, args)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.dry_run:
        print(f"Validated {len(training)} training examples and {len(validation)} inputs; no models run or files written.")
        return

    targets = ([args.output] if not args.retrieve_only else [])
    if args.neighbors_output:
        targets.append(args.neighbors_output)
    if len({path.resolve() for path in targets}) != len(targets):
        parser.error("Prediction and neighbor outputs must be different paths")
    for path in targets:
        if path.exists():
            parser.error(f"Output already exists; choose another path: {path}")
    if not args.retrieve_only and not os.environ.get("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY in your environment")

    if neighbors is None:
        print(f"Retrieving top-{min(args.top_k, len(training))} examples per input", file=sys.stderr)
        neighbors = retrieve_neighbors(training, validation, args.embedding_model,
                                       args.top_k, args.batch_size)
    if args.neighbors_output:
        save_neighbors(args.neighbors_output, neighbors)
        print(f"Saved neighbors to {args.neighbors_output}")
    if args.retrieve_only:
        return

    from openai import OpenAI

    client = OpenAI()  # Reads OPENAI_API_KEY from the environment.
    outputs = []
    for index, (text, indices) in enumerate(zip(validation, neighbors)):
        completion = client.chat.completions.create(
            model=args.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": build_prompt(TASK, training, text, indices)}],
            max_tokens=args.max_tokens,
            temperature=0.0,
            n=1,
        )
        choice = completion.choices[0]
        if choice.finish_reason != "stop" or not choice.message.content:
            raise RuntimeError(f"Input {index}: response incomplete or empty ({choice.finish_reason}); predictions not saved")
        outputs.append(choice.message.content)
        print(f"Completed {index + 1}/{len(validation)}", file=sys.stderr)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(outputs, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Saved {len(outputs)} predictions to {args.output}")


if __name__ == "__main__":
    run()

