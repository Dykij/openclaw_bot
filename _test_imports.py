import traceback, sys

with open("_imp_result.txt", "w") as f:
    try:
        from src.deep_research import DeepResearchPipeline, EvidencePiece, ResearchState
        f.write(f"facade OK: {DeepResearchPipeline}\n")
    except Exception:
        traceback.print_exc(file=f)

    try:
        from src.research import DeepResearchPipeline, EvidencePiece, ResearchState
        f.write(f"package OK: {DeepResearchPipeline}\n")
    except Exception:
        traceback.print_exc(file=f)

f2 = open("_imp_result.txt")
print(f2.read())
f2.close()
