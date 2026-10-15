from fastapi import APIRouter, HTTPException
from backend.storage.database import runs
from backend.research.protocol import release, readiness
from backend.research.statistics import analyse

router = APIRouter(prefix="/api/research", tags=["research"])


@router.get("/release")
def current_release():
    try:
        return release()
    except ValueError as e:
        raise HTTPException(409, str(e))


@router.get("/readiness")
def report():
    return readiness()


@router.get("/analysis")
def analysis(protocol: str | None = None):
    return analyse(runs(), release(), protocol)


@router.get("/export")
def export(protocol: str | None = None):
    from fastapi.responses import Response
    from backend.research.export import bundle

    try:
        return Response(
            bundle(runs(), protocol),
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="checkoutbench-research.zip"'
            },
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
