"""Knowledge Store — Semantic knowledge base for language standards.

Stores structured knowledge entries (Python 3.14, Rust 2024 Edition, etc.)
so the agent can reference best practices, new APIs, deprecated patterns,
and migration guidance during code generation and review.

Tags:
  STANDARD_LIBRARY_PY314  — Python 3.14 features & best practices
  RUST_STABLE_2026        — Rust 2024 Edition (1.85+) features & patterns
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import structlog

logger = structlog.get_logger("KnowledgeStore")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeEntry:
    """A single piece of knowledge about a language feature."""
    id: str                          # unique key, e.g. "py314_pep649"
    tag: str                         # e.g. STANDARD_LIBRARY_PY314
    category: str                    # e.g. "annotation", "asyncio", "safety"
    title: str                       # human-readable title
    summary: str                     # 1-3 sentence description
    best_practice: str               # what to do / how to use it
    code_example: str = ""           # illustrative code snippet
    anti_pattern: str = ""           # what NOT to do (deprecated pattern)
    migration_note: str = ""         # how to migrate from old pattern
    pep_or_rfc: str = ""             # reference PEP/RFC
    added_at: float = field(default_factory=time.time)


@dataclass
class KnowledgeIndex:
    """In-memory index of all knowledge entries."""
    entries: List[KnowledgeEntry] = field(default_factory=list)
    version: str = "12.0-ASCENDED"
    built_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Built-in knowledge: Python 3.14
# ---------------------------------------------------------------------------

_PY314_ENTRIES: List[KnowledgeEntry] = [
    KnowledgeEntry(
        id="py314_pep649",
        tag="STANDARD_LIBRARY_PY314",
        category="annotation",
        title="PEP 649 & 749: Deferred Evaluation of Annotations",
        summary=(
            "Annotations on functions, classes, and modules are no longer evaluated eagerly. "
            "They are stored as annotate functions and evaluated only when needed. "
            "Forward references no longer need string quotes."
        ),
        best_practice=(
            "Remove quotes from forward-reference annotations. "
            "Use annotationlib.get_annotations() with Format.FORWARDREF for safe introspection. "
            "Remove 'from __future__ import annotations' when targeting 3.14+."
        ),
        code_example=(
            "from annotationlib import get_annotations, Format\n"
            "def func(arg: MyClass) -> Result:  # no quotes needed\n"
            "    pass\n"
            "# Safe introspection:\n"
            "anns = get_annotations(func, format=Format.FORWARDREF)"
        ),
        anti_pattern=(
            "Do NOT read __annotations__ directly from namespace dicts. "
            "Do NOT rely on from __future__ import annotations (deprecated)."
        ),
        migration_note=(
            "Replace typing.get_type_hints() with annotationlib.get_annotations(). "
            "from __future__ import annotations still works but is deprecated."
        ),
        pep_or_rfc="PEP 649, PEP 749",
    ),
    KnowledgeEntry(
        id="py314_pep750",
        tag="STANDARD_LIBRARY_PY314",
        category="strings",
        title="PEP 750: Template String Literals (t-strings)",
        summary=(
            "Template strings (t-strings) use t'...' prefix and return a Template object "
            "instead of str. They allow custom processing of string interpolation for "
            "sanitization, DSLs, HTML escaping, SQL safety."
        ),
        best_practice=(
            "Use t-strings for user-input sanitization in SQL, HTML, shell commands. "
            "Iterate Template to access static parts and Interpolation objects. "
            "Use string.templatelib.Template and Interpolation for processing."
        ),
        code_example=(
            "from string.templatelib import Interpolation\n"
            "name = 'user_input'\n"
            "template = t'Hello {name}'\n"
            "for part in template:\n"
            "    if isinstance(part, Interpolation):\n"
            "        print(f'Value: {part.value}')"
        ),
        anti_pattern="Do NOT use f-strings when you need to sanitize user input.",
        pep_or_rfc="PEP 750",
    ),
    KnowledgeEntry(
        id="py314_pep734",
        tag="STANDARD_LIBRARY_PY314",
        category="concurrency",
        title="PEP 734: Multiple Interpreters (concurrent.interpreters)",
        summary=(
            "The concurrent.interpreters module exposes CPython subinterpreters "
            "for true multi-core parallelism without GIL contention. "
            "Think of it as threads with process-like isolation."
        ),
        best_practice=(
            "Use concurrent.interpreters for CPU-intensive parallel work. "
            "Use InterpreterPoolExecutor from concurrent.futures for pool-based usage. "
            "Prefer interpreters over multiprocessing for lower overhead."
        ),
        code_example=(
            "import concurrent.interpreters as interpreters\n"
            "from concurrent.futures import InterpreterPoolExecutor\n"
            "with InterpreterPoolExecutor() as executor:\n"
            "    results = list(executor.map(cpu_heavy_fn, data_chunks))"
        ),
        anti_pattern=(
            "Do NOT share mutable state between interpreters (they are isolated). "
            "Do NOT expect third-party C extensions to work across interpreters yet."
        ),
        pep_or_rfc="PEP 734",
    ),
    KnowledgeEntry(
        id="py314_pep768",
        tag="STANDARD_LIBRARY_PY314",
        category="debugging",
        title="PEP 768: Safe External Debugger Interface (sys.remote_exec)",
        summary=(
            "Zero-overhead debugging interface allows debuggers and profilers to safely "
            "attach to running Python processes without stopping or restarting them. "
            "Uses sys.remote_exec() for remote code injection."
        ),
        best_practice=(
            "Use sys.remote_exec() for production debugging instead of invasive alternatives. "
            "Use 'python -m asyncio pstree PID' for async task tree visualization."
        ),
        code_example=(
            "import sys\n"
            "# Attach debugger to process with PID 1234\n"
            "# sys.remote_exec(1234, '/tmp/debug_script.py')\n"
            "# Async introspection:\n"
            "# python -m asyncio pstree <PID>"
        ),
        pep_or_rfc="PEP 768",
    ),
    KnowledgeEntry(
        id="py314_asyncio",
        tag="STANDARD_LIBRARY_PY314",
        category="asyncio",
        title="Asyncio Improvements: Introspection, Free-threading, Performance",
        summary=(
            "asyncio now has capture_call_graph()/print_call_graph() for introspection, "
            "10-20% performance improvement via native task linked list, "
            "first-class free-threading support with parallel event loops, "
            "and get_event_loop() now raises RuntimeError if no loop."
        ),
        best_practice=(
            "Always use asyncio.run() or asyncio.Runner, never get_event_loop(). "
            "Use capture_call_graph() for debugging async programs. "
            "Use asyncio.run(main(), loop_factory=...) instead of event loop policies. "
            "create_task() now accepts arbitrary kwargs passed to Task constructor."
        ),
        code_example=(
            "import asyncio\n\n"
            "async def main():\n"
            "    # New introspection\n"
            "    graph = asyncio.capture_call_graph()\n"
            "    asyncio.print_call_graph()\n\n"
            "asyncio.run(main())  # ALWAYS use asyncio.run()"
        ),
        anti_pattern=(
            "REMOVED: asyncio.get_event_loop() no longer creates loops implicitly. "
            "DEPRECATED: asyncio.iscoroutinefunction() — use inspect.iscoroutinefunction(). "
            "DEPRECATED: event loop policy system (removal in 3.16). "
            "REMOVED: ChildWatcher classes (FastChildWatcher, SafeChildWatcher, etc.)."
        ),
        migration_note=(
            "Replace loop = asyncio.get_event_loop(); loop.run_until_complete(main()) "
            "with asyncio.run(main()). "
            "Replace event loop policies with asyncio.run(main(), loop_factory=...)."
        ),
        pep_or_rfc="",
    ),
    KnowledgeEntry(
        id="py314_pep758",
        tag="STANDARD_LIBRARY_PY314",
        category="syntax",
        title="PEP 758: except/except* Without Brackets",
        summary="except ValueError, TypeError: is now valid without parentheses.",
        best_practice="Use 'except ValueError, TypeError:' for cleaner syntax in 3.14+.",
        code_example="try:\n    ...\nexcept ValueError, TypeError:\n    handle()",
        pep_or_rfc="PEP 758",
    ),
    KnowledgeEntry(
        id="py314_pep765",
        tag="STANDARD_LIBRARY_PY314",
        category="safety",
        title="PEP 765: Control Flow in finally Blocks Warning",
        summary="return/break/continue in finally blocks now emit SyntaxWarning.",
        best_practice="Avoid return, break, or continue inside finally blocks.",
        anti_pattern="def f():\n    try: ...\n    finally: return 1  # SyntaxWarning",
        pep_or_rfc="PEP 765",
    ),
    KnowledgeEntry(
        id="py314_pep784",
        tag="STANDARD_LIBRARY_PY314",
        category="compression",
        title="PEP 784: Zstandard (compression.zstd) in stdlib",
        summary="Zstandard compression is now in the standard library via compression.zstd.",
        best_practice="Use compression.zstd instead of third-party python-zstandard for new code.",
        code_example="import compression.zstd\ndata = compression.zstd.compress(b'hello world')",
        pep_or_rfc="PEP 784",
    ),
    KnowledgeEntry(
        id="py314_free_threading",
        tag="STANDARD_LIBRARY_PY314",
        category="concurrency",
        title="Free-Threaded Python (PEP 703/779) Officially Supported",
        summary=(
            "Free-threaded mode (no GIL) is officially supported in 3.14. "
            "Specializing adaptive interpreter enabled, 5-10% single-thread penalty. "
            "PyO3, Cython, pybind11 adapting."
        ),
        best_practice=(
            "Test your code with free-threaded build for true parallelism. "
            "Extension modules should use Py_mod_gil slot. "
            "Check third-party library compat before enabling."
        ),
        pep_or_rfc="PEP 703, PEP 779",
    ),
    KnowledgeEntry(
        id="py314_new_modules",
        tag="STANDARD_LIBRARY_PY314",
        category="stdlib",
        title="New Modules: annotationlib, compression, concurrent.interpreters, string.templatelib",
        summary=(
            "Four new stdlib modules: annotationlib (annotation introspection), "
            "compression/compression.zstd (Zstandard), "
            "concurrent.interpreters (subinterpreters), "
            "string.templatelib (t-string support)."
        ),
        best_practice="Import from these new modules directly; no third-party deps needed.",
        code_example="import annotationlib\nimport compression.zstd\nimport concurrent.interpreters\nfrom string.templatelib import Template",
        pep_or_rfc="PEP 749, PEP 784, PEP 734, PEP 750",
    ),
    KnowledgeEntry(
        id="py314_typing_union",
        tag="STANDARD_LIBRARY_PY314",
        category="typing",
        title="types.UnionType ≡ typing.Union (Unified)",
        summary=(
            "types.UnionType and typing.Union are now aliases. "
            "Both Union[int, str] and int | str create the same type. "
            "repr is now always 'int | str'."
        ),
        best_practice=(
            "Prefer int | str syntax over Union[int, str]. "
            "Use typing.get_origin() and typing.get_args() for introspection."
        ),
        anti_pattern="Do NOT rely on typing._UnionGenericAlias (removed in 3.17).",
        pep_or_rfc="",
    ),
    KnowledgeEntry(
        id="py314_functools",
        tag="STANDARD_LIBRARY_PY314",
        category="stdlib",
        title="functools.Placeholder for Partial Application",
        summary="functools.Placeholder allows reserving positional argument slots in partial().",
        best_practice="Use functools.Placeholder with partial() for flexible partial application.",
        code_example=(
            "from functools import partial, Placeholder\n"
            "f = partial(pow, Placeholder, 2)  # f(x) == pow(x, 2)"
        ),
        pep_or_rfc="",
    ),
    KnowledgeEntry(
        id="py314_pep741",
        tag="STANDARD_LIBRARY_PY314",
        category="c_api",
        title="PEP 741: Python Configuration C API",
        summary=(
            "New C API for reading/setting Python runtime configuration: "
            "PyConfig_Get(), PyConfig_Set(), PyInitConfig_Create(), etc. "
            "Legacy Py_*Flag globals deprecated."
        ),
        best_practice="Use PyConfig_Get/Set instead of legacy Py_*Flag globals in C extensions.",
        pep_or_rfc="PEP 741",
    ),
]


# ---------------------------------------------------------------------------
# Built-in knowledge: Rust 2024 Edition
# ---------------------------------------------------------------------------

_RUST2024_ENTRIES: List[KnowledgeEntry] = [
    KnowledgeEntry(
        id="rust2024_rpit_lifetime",
        tag="RUST_STABLE_2026",
        category="lifetimes",
        title="RPIT Lifetime Capture Rules (RFC 3498)",
        summary=(
            "In Rust 2024, all in-scope generic parameters including lifetimes "
            "are implicitly captured in return-position impl Trait when use<..> "
            "is not present. This is consistent with RPITIT and async fn."
        ),
        best_practice=(
            "Use use<..> bounds to explicitly control lifetime capture. "
            "Remove Captures trick and outlives trick — use use<..> or omit entirely. "
            "Run 'cargo fix --edition' to auto-insert use<..> where needed."
        ),
        code_example=(
            "// Rust 2024: lifetime implicitly captured\n"
            "fn f<'a>(x: &'a ()) -> impl Sized { *x }\n"
            "// Explicit control:\n"
            "fn g<'a>(x: &'a ()) -> impl Sized + use<> { *x }"
        ),
        anti_pattern=(
            "Do NOT use the Captures<> trick — use use<..> instead. "
            "Do NOT add unnecessary T: 'a bounds for the outlives trick."
        ),
        migration_note="Run 'cargo fix --edition' — impl_trait_overcaptures lint auto-fixes.",
        pep_or_rfc="RFC 3498, RFC 3617",
    ),
    KnowledgeEntry(
        id="rust2024_unsafe_extern",
        tag="RUST_STABLE_2026",
        category="safety",
        title="Unsafe Extern Blocks Required (RFC 3484)",
        summary=(
            "extern blocks must now be marked with 'unsafe' keyword. "
            "Individual items can be marked 'safe' or 'unsafe'. "
            "Items marked 'safe' can be used without unsafe block."
        ),
        best_practice=(
            "Always prefix extern blocks with 'unsafe'. "
            "Mark individual FFI items as 'pub safe fn' when they have no safety requirements. "
            "Run 'cargo fix --edition' to auto-add 'unsafe' keyword."
        ),
        code_example=(
            "unsafe extern \"C\" {\n"
            "    pub safe fn sqrt(x: f64) -> f64;\n"
            "    pub unsafe fn strlen(p: *const c_char) -> usize;\n"
            "}"
        ),
        anti_pattern="Do NOT write 'extern \"C\" { ... }' without 'unsafe' prefix.",
        migration_note="missing_unsafe_on_extern lint auto-fixes via cargo fix --edition.",
        pep_or_rfc="RFC 3484",
    ),
    KnowledgeEntry(
        id="rust2024_never_type",
        tag="RUST_STABLE_2026",
        category="type_system",
        title="Never Type Fallback Change",
        summary=(
            "Never type (!) to-any coercions now fall back to ! instead of (). "
            "never_type_fallback_flowing_into_unsafe lint is now deny-by-default."
        ),
        best_practice=(
            "Explicitly specify types when using f()? where f is generic over Ok type. "
            "Use f::<()>()? or () = f()? to avoid ! fallback issues. "
            "In closures: run(|| -> () { panic!() }) to specify return type."
        ),
        code_example=(
            "// Before (relied on () fallback):\n"
            "// f()?;  // T inferred as () — now inferred as !\n"
            "// After:\n"
            "f::<()>()?;  // explicit\n"
            "// Closure fix:\n"
            "run(|| -> () { panic!() });"
        ),
        anti_pattern="Do NOT rely on implicit () fallback from never type coercions.",
        migration_note="No auto-fix. Check warnings on previous edition, specify types explicitly.",
        pep_or_rfc="",
    ),
    KnowledgeEntry(
        id="rust2024_gen_keyword",
        tag="RUST_STABLE_2026",
        category="syntax",
        title="gen Keyword Reserved (RFC 3513)",
        summary=(
            "'gen' is now a reserved keyword for future gen blocks (iterators). "
            "Existing identifiers named 'gen' must use r#gen."
        ),
        best_practice="Rename any 'gen' identifiers to avoid conflict, or use r#gen.",
        code_example="fn r#gen() { /* renamed from gen() */ }",
        anti_pattern="Do NOT name functions, variables, or modules 'gen'.",
        migration_note="keyword_idents_2024 lint auto-fixes via cargo fix --edition.",
        pep_or_rfc="RFC 3513",
    ),
    KnowledgeEntry(
        id="rust2024_intoiterator_box_slice",
        tag="RUST_STABLE_2026",
        category="iterators",
        title="IntoIterator for Box<[T]> by-value",
        summary=(
            "Box<[T]>.into_iter() now yields owned T values in Rust 2024, "
            "not &T references as in previous editions."
        ),
        best_practice=(
            "Use .iter() when you want references from boxed slices. "
            "Use .into_iter() or 'for x in boxed_slice' for by-value iteration."
        ),
        code_example=(
            "let s: Box<[u32]> = vec![1, 2, 3].into_boxed_slice();\n"
            "for x in s { /* x: u32 (owned) in 2024 */ }"
        ),
        anti_pattern="boxed_slice.into_iter() yields &T in old editions — check when upgrading.",
        migration_note="boxed_slice_into_iter lint auto-fixes .into_iter() to .iter().",
        pep_or_rfc="",
    ),
    KnowledgeEntry(
        id="rust2024_unsafe_attributes",
        tag="RUST_STABLE_2026",
        category="safety",
        title="Unsafe Attributes (RFC 3325)",
        summary=(
            "Some attributes like #[no_mangle] and #[export_name] now require "
            "'unsafe' prefix: #[unsafe(no_mangle)]."
        ),
        best_practice=(
            "Prefix safety-critical attributes with unsafe(). "
            "Run 'cargo fix --edition' to auto-add unsafe() wrapper."
        ),
        code_example='#[unsafe(no_mangle)]\npub extern "C" fn my_fn() {}',
        anti_pattern="Do NOT use #[no_mangle] without unsafe() in Rust 2024.",
        pep_or_rfc="RFC 3325",
    ),
    KnowledgeEntry(
        id="rust2024_static_mut",
        tag="RUST_STABLE_2026",
        category="safety",
        title="Disallow References to static mut",
        summary=(
            "Creating references to static mut items is now a hard error. "
            "Use raw pointers (addr_of!/addr_of_mut!) or std::sync types instead."
        ),
        best_practice=(
            "Replace &STATIC_MUT with addr_of!(STATIC_MUT). "
            "Prefer std::sync::Mutex, OnceLock, or AtomicXxx over static mut."
        ),
        code_example=(
            "use std::ptr::addr_of;\n"
            "static mut COUNTER: u32 = 0;\n"
            "let ptr = addr_of!(COUNTER);  // OK\n"
            "// let r = &COUNTER;  // ERROR in 2024"
        ),
        anti_pattern="NEVER create references (&/&mut) to static mut items.",
        pep_or_rfc="",
    ),
    KnowledgeEntry(
        id="rust2024_match_ergonomics",
        tag="RUST_STABLE_2026",
        category="patterns",
        title="Match Ergonomics Restrictions (Edition 2024)",
        summary=(
            "In Rust 2024, certain match ergonomics patterns that could silently "
            "change mutability or reference behavior are restricted."
        ),
        best_practice="Be explicit about & and ref in match patterns to avoid ambiguity.",
        pep_or_rfc="",
    ),
    KnowledgeEntry(
        id="rust2024_prelude",
        tag="RUST_STABLE_2026",
        category="stdlib",
        title="Rust 2024 Prelude Additions",
        summary=(
            "The 2024 edition prelude adds Future and IntoFuture traits. "
            "This brings async patterns into scope by default."
        ),
        best_practice=(
            "Future and IntoFuture are now in prelude — no manual import needed. "
            "Check for name conflicts with custom Future/IntoFuture traits."
        ),
        migration_note="Run cargo fix --edition to resolve any name conflicts.",
        pep_or_rfc="",
    ),
    KnowledgeEntry(
        id="rust2024_tail_expressions",
        tag="RUST_STABLE_2026",
        category="safety",
        title="Temporary Lifetimes in Tail Expressions",
        summary=(
            "Temporaries in tail expressions of blocks used as the last statement "
            "may have their lifetimes extended or restricted based on new drop rules."
        ),
        best_practice="Store temporaries in local variables if you need precise drop timing.",
        pep_or_rfc="",
    ),
]


# ---------------------------------------------------------------------------
# Knowledge Store
# ---------------------------------------------------------------------------

_DEFAULT_STORE_PATH = "data/knowledge_store.json"


class KnowledgeStore:
    """Manages structured knowledge entries for language standards.

    Usage:
        store = KnowledgeStore(project_root="/path/to/project")
        store.build()
        entries = store.query(tag="STANDARD_LIBRARY_PY314")
        store.save()
    """

    def __init__(self, project_root: str, store_path: Optional[str] = None):
        self.project_root = os.path.abspath(project_root)
        self.store_path = os.path.join(
            self.project_root,
            store_path or _DEFAULT_STORE_PATH,
        )
        self.index = KnowledgeIndex()

    def build(self) -> KnowledgeIndex:
        """Load built-in knowledge entries and any previously saved ones."""
        # Start with built-in knowledge
        built_in = _PY314_ENTRIES + _RUST2024_ENTRIES
        existing_ids: Set[str] = set()

        # Load previously saved entries
        if os.path.exists(self.store_path):
            try:
                with open(self.store_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for entry_dict in data.get("entries", []):
                    entry = KnowledgeEntry(**entry_dict)
                    existing_ids.add(entry.id)
                    self.index.entries.append(entry)
            except (json.JSONDecodeError, TypeError, KeyError):
                pass

        # Add built-in entries that aren't already stored
        for entry in built_in:
            if entry.id not in existing_ids:
                self.index.entries.append(entry)
                existing_ids.add(entry.id)

        self.index.built_at = time.time()
        logger.info(
            "knowledge_store_built",
            total_entries=len(self.index.entries),
            py314=sum(1 for e in self.index.entries if e.tag == "STANDARD_LIBRARY_PY314"),
            rust2024=sum(1 for e in self.index.entries if e.tag == "RUST_STABLE_2026"),
        )
        return self.index

    def save(self) -> str:
        """Persist knowledge index to disk."""
        os.makedirs(os.path.dirname(self.store_path), exist_ok=True)
        data = {
            "version": self.index.version,
            "built_at": self.index.built_at,
            "entries": [asdict(e) for e in self.index.entries],
        }
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("knowledge_store_saved", path=self.store_path)
        return self.store_path

    def query(
        self,
        tag: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> List[KnowledgeEntry]:
        """Query knowledge entries by tag, category, or keyword."""
        results = self.index.entries
        if tag:
            results = [e for e in results if e.tag == tag]
        if category:
            results = [e for e in results if e.category == category]
        if keyword:
            kw = keyword.lower()
            results = [
                e for e in results
                if kw in e.title.lower()
                or kw in e.summary.lower()
                or kw in e.best_practice.lower()
                or kw in e.code_example.lower()
            ]
        return results

    def get_best_practices(self, tag: str) -> List[Dict[str, str]]:
        """Extract best practices for a given tag, suitable for agent injection."""
        entries = self.query(tag=tag)
        return [
            {
                "title": e.title,
                "best_practice": e.best_practice,
                "anti_pattern": e.anti_pattern,
                "code_example": e.code_example,
            }
            for e in entries
            if e.best_practice
        ]

    def get_context_for_prompt(self, tags: List[str], max_entries: int = 10) -> str:
        """Generate a context block suitable for LLM prompt injection."""
        entries: List[KnowledgeEntry] = []
        for tag in tags:
            entries.extend(self.query(tag=tag))

        entries = entries[:max_entries]
        if not entries:
            return ""

        lines = ["## Knowledge Context (Auto-injected)\n"]
        for e in entries:
            lines.append(f"### {e.title}")
            lines.append(e.summary)
            if e.best_practice:
                lines.append(f"**Best Practice:** {e.best_practice}")
            if e.anti_pattern:
                lines.append(f"**Avoid:** {e.anti_pattern}")
            if e.code_example:
                lines.append(f"```\n{e.code_example}\n```")
            lines.append("")
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        """Return summary statistics."""
        by_tag: Dict[str, int] = {}
        by_cat: Dict[str, int] = {}
        for e in self.index.entries:
            by_tag[e.tag] = by_tag.get(e.tag, 0) + 1
            by_cat[e.category] = by_cat.get(e.category, 0) + 1
        return {
            "total_entries": len(self.index.entries),
            "by_tag": by_tag,
            "by_category": by_cat,
            "version": self.index.version,
        }
