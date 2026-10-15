from fastapi import APIRouter, HTTPException
from backend.storage.database import runs
from backend.research.protocol import release, readiness

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
def analysis():
    from backend.research.official import dataset
    return dataset(runs())


@router.get("/export")
def export():
    from fastapi.responses import Response
    from backend.research.export import bundle

    try:
        return Response(
            bundle(runs()),
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="checkoutbench-research.zip"'
            },
        )
    except ValueError as e:
        raise HTTPException(409, str(e))
