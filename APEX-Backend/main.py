
if __name__ == "__main__":
    import uvicorn
    from pathlib import Path
    backend_dir = Path(__file__).resolve().parent
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_dirs=[str(backend_dir / "app")],
        reload_excludes=["storage/*", "storage/**", "logs/*", "*.json"],
    )
