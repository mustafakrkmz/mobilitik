from __future__ import annotations

import argparse
import os

from mobilitik.analysis.nlp_store import SentimentStore
from mobilitik.analysis.sentiment import (
    ANALYZER_VERSION,
    DEFAULT_MODEL_ID,
    aggregate_aspect_sentiment,
    aspect_fingerprint,
    aspect_sentence_map,
    complaint_text,
    scores_from_pipeline_output,
    text_fingerprint,
)
from mobilitik.company import normalize_company_input
from mobilitik.desktop.data import ComplaintRepository


def _load_classifier(model_id: str):
    try:
        import torch
        from transformers import pipeline
    except ImportError as exc:
        raise RuntimeError(
            "NLP bileşenleri kurulu değil. Mobilitik'teki 'NLP Bileşenlerini Kur / Güncelle' düğmesini kullanın."
        ) from exc

    cpu_count = os.cpu_count() or 1
    torch.set_num_threads(max(1, min(8, cpu_count)))
    return pipeline(
        "text-classification",
        model=model_id,
        tokenizer=model_id,
        device=-1,
    )


def _predict(classifier, texts: list[str]):
    if not texts:
        return []
    outputs = classifier(
        texts,
        top_k=None,
        truncation=True,
        max_length=512,
        batch_size=min(8, max(1, len(texts))),
    )
    # HF returns list[dict] for one text on some versions and list[list[dict]]
    # for batches. Mobilitik always normalizes to one score object per input.
    if outputs and isinstance(outputs[0], dict):
        outputs = [outputs]
    return [scores_from_pipeline_output(rows) for rows in outputs]


def run(
    *,
    db_path: str,
    company: str,
    start_date: str,
    end_date: str,
    model_id: str = DEFAULT_MODEL_ID,
) -> int:
    company_slug = normalize_company_input(company)
    repo = ComplaintRepository(db_path)
    store = SentimentStore(db_path)
    records = [dict(row) for row in repo.filtered_complaints(company_slug, start_date, end_date)]

    jobs: list[dict] = []
    cached_count = 0
    for record in records:
        text = complaint_text(record.get("title"), record.get("complaint_text"))
        if not text:
            continue
        sentiment_hash = text_fingerprint(record.get("title"), record.get("complaint_text"))
        aspect_hash = aspect_fingerprint(record.get("title"), record.get("complaint_text"))
        sentiment_current = (
            store.cached_hash(record["id"], model_id, ANALYZER_VERSION) == sentiment_hash
        )
        aspect_current = (
            store.aspect_cached_hash(record["id"], model_id, ANALYZER_VERSION) == aspect_hash
        )
        if sentiment_current and aspect_current:
            cached_count += 1
            continue
        jobs.append(
            {
                "record": record,
                "text": text,
                "sentiment_hash": sentiment_hash,
                "aspect_hash": aspect_hash,
                "sentiment_needed": not sentiment_current,
                "aspect_needed": not aspect_current,
            }
        )

    print(
        f"NLP_STATUS Seçili dönemde {len(records)} kayıt; {cached_count} önbellekte; {len(jobs)} analiz edilecek.",
        flush=True,
    )

    if not jobs:
        print(f"NLP_DONE {len(records)} 0 {cached_count}", flush=True)
        return 0

    try:
        print(f"NLP_STATUS Model hazırlanıyor: {model_id}", flush=True)
        classifier = _load_classifier(model_id)
    except Exception as exc:
        print(f"NLP_ERROR {exc}", flush=True)
        return 2

    total = len(jobs)
    completed = 0
    for job in jobs:
        record = job["record"]
        try:
            sentence_map = aspect_sentence_map(record.get("title"), record.get("complaint_text"))
            inference_texts: list[str] = []
            full_index: int | None = None
            sentence_offset: int | None = None

            if job["sentiment_needed"]:
                full_index = len(inference_texts)
                inference_texts.append(job["text"])

            if job["aspect_needed"]:
                sentence_offset = len(inference_texts)
                inference_texts.extend(sentence for sentence, _categories in sentence_map)

            predictions = _predict(classifier, inference_texts)

            if full_index is not None:
                score = predictions[full_index]
                store.upsert_sentiment(
                    record["id"],
                    model_id,
                    ANALYZER_VERSION,
                    job["sentiment_hash"],
                    label=score.label,
                    confidence=score.confidence,
                    negative=score.negative,
                    neutral=score.neutral,
                    positive=score.positive,
                )

            if sentence_offset is not None:
                sentence_scores = predictions[sentence_offset:]
                paired = [
                    (categories, score)
                    for (_sentence, categories), score in zip(sentence_map, sentence_scores)
                ]
                aspects = aggregate_aspect_sentiment(paired)
                store.replace_aspects(
                    record["id"],
                    model_id,
                    ANALYZER_VERSION,
                    job["aspect_hash"],
                    [
                        {
                            "category": aspect.category,
                            "sentence_count": aspect.sentence_count,
                            "negative": aspect.negative,
                            "neutral": aspect.neutral,
                            "positive": aspect.positive,
                        }
                        for aspect in aspects
                    ],
                )

        except Exception as exc:
            print(
                f"NLP_WARNING Kayıt {record.get('id')} analiz edilemedi: {exc}",
                flush=True,
            )

        completed += 1
        print(f"NLP_PROGRESS {completed} {total}", flush=True)

    print(f"NLP_DONE {len(records)} {completed} {cached_count}", flush=True)
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Mobilitik on-demand Turkish sentiment analysis worker")
    parser.add_argument("--db", default="mobilitik.db")
    parser.add_argument("--company", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL_ID)
    return parser


def main():
    args = build_parser().parse_args()
    raise SystemExit(
        run(
            db_path=args.db,
            company=args.company,
            start_date=args.start_date,
            end_date=args.end_date,
            model_id=args.model,
        )
    )


if __name__ == "__main__":
    main()
