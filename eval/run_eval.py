import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from main import search_chunks
from eval.eval_set import EVAL_CASES


def run():
    correct = 0
    results = []

    for case in EVAL_CASES:
        found = search_chunks(case["question"], top_k=3)
        hit = case["expected_source"] in found.sources
        correct += hit
        results.append({
            "question": case["question"],
            "expected": case["expected_source"],
            "retrieved_sources": found.sources,
            "hit": hit,
        })

    print("=" * 60)
    for r in results:
        status = "PASS" if r["hit"] else "FAIL"
        print(f"[{status}] {r['question']}")
        print(f"  expected: {r['expected']}")
        print(f"  got:      {r['retrieved_sources']}")
        print()

    accuracy = 100 * correct / len(EVAL_CASES)
    print("=" * 60)
    print(f"Retrieval accuracy: {correct}/{len(EVAL_CASES)} ({accuracy:.0f}%)")


if __name__ == "__main__":
    run()