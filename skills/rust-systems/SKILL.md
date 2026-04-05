---
name: rust-systems
description: "Rust systems programming: 2024 edition, async traits, ownership patterns, unsafe boundaries, FFI, performance. Use when: writing/reviewing Rust code, designing zero-cost abstractions, implementing FFI bridges, optimizing hot paths."
version: 1.0.0
---

# Rust Systems Programming

## Purpose

Expert Rust development with 2024 Edition standards, async patterns, and systems-level optimization.

## Rust 2024 Edition (MUST apply)

1. **RPIT lifetime capture rules**: Return-position `impl Trait` captures all in-scope lifetimes by default. Use `+ use<'a>` to restrict.
2. **`unsafe extern` blocks**: All `extern` blocks require `unsafe extern` keyword.
3. **`gen` keyword reserved**: For future generator support; don't use as identifier.
4. **Never type `!` stabilized**: Use for functions that never return.
5. **`IntoIterator` for `Box<[T]>`**: Boxes of slices are now directly iterable.
6. **Lifetime elision in `async fn`**: Better defaults for async function lifetimes.

## Ownership & Borrowing Patterns

```rust
// Prefer borrowing over cloning
fn process(data: &[u8]) -> Result<Output> { ... }

// Use Cow for optional ownership
use std::borrow::Cow;
fn normalize(input: &str) -> Cow<'_, str> {
    if input.contains(' ') {
        Cow::Owned(input.replace(' ', "_"))
    } else {
        Cow::Borrowed(input)
    }
}

// RAII pattern for resource management
struct Connection { /* ... */ }
impl Drop for Connection {
    fn drop(&mut self) { self.close(); }
}
```

## Async Patterns

```rust
// Use async traits (stabilized)
trait DataStore {
    async fn get(&self, key: &str) -> Option<Vec<u8>>;
    async fn set(&self, key: &str, value: &[u8]) -> Result<()>;
}

// Structured concurrency with tokio
let (a, b) = tokio::join!(fetch_data(), process_queue());

// Cancellation-safe select
tokio::select! {
    result = operation() => handle(result),
    _ = tokio::time::sleep(Duration::from_secs(30)) => timeout(),
}
```

## Error Handling

```rust
// Use thiserror for library errors
#[derive(thiserror::Error, Debug)]
enum AppError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Parse error at line {line}: {msg}")]
    Parse { line: usize, msg: String },
}

// Use anyhow for application errors
fn main() -> anyhow::Result<()> {
    let config = load_config().context("Failed to load config")?;
    Ok(())
}
```

## Performance Rules

1. **Measure first**: Use `criterion` for benchmarks, `flamegraph` for profiling
2. **Avoid allocations in hot paths**: Use `&str` over `String`, `&[T]` over `Vec<T>`
3. **Use `#[inline]` sparingly**: Only on small, frequently-called functions
4. **Prefer stack allocation**: Use arrays over Vec when size is known
5. **Use `SmallVec`** for typically-small collections
6. **Edition = "2024"** in all Cargo.toml files

## FFI / Unsafe Boundaries

```rust
// Minimize unsafe surface area
unsafe extern "C" {
    fn external_func(ptr: *const u8, len: usize) -> i32;
}

// Safe wrapper
fn call_external(data: &[u8]) -> Result<i32> {
    let result = unsafe { external_func(data.as_ptr(), data.len()) };
    if result < 0 { Err(Error::External(result)) } else { Ok(result) }
}
```
