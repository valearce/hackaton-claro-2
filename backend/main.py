"""API del motor NBA: OR-Tools, versiones persistentes y exportaciones."""
from pathlib import Path
import sys

SERVICE=Path(__file__).resolve().parent
sys.path.insert(0,str(SERVICE if (SERVICE/"modelo").is_dir() else SERVICE.parent))
from dotenv import load_dotenv
load_dotenv(SERVICE.parent/".env.local",override=False)

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
import gzip
import io
import logging
from typing import Literal

try:
    from . import servicio as svc
    from .esquemas import Configuracion, Pedido, Guardar, diccionario
except ImportError:
    import servicio as svc
    from esquemas import Configuracion, Pedido, Guardar, diccionario

app=FastAPI(title="Consola NBA Claro",version="1.0.0")


@app.exception_handler(RequestValidationError)
async def invalid_request(request,error):
    details=[".".join(str(p) for p in item["loc"] if p!="body")+": "+item["msg"] for item in error.errors()[:6]]
    return JSONResponse(status_code=422,content={"detail":"; ".join(details)})


@app.exception_handler(ValueError)
async def invalid_value(request,error):
    return JSONResponse(status_code=400,content={"detail":str(error)})


@app.exception_handler(FileNotFoundError)
async def missing(request,error):
    return JSONResponse(status_code=404,content={"detail":str(error)})


@app.exception_handler(TimeoutError)
async def busy(request,error):
    return JSONResponse(status_code=503,content={"detail":str(error)},headers={"Retry-After":"3"})


@app.exception_handler(Exception)
async def service_error(request,error):
    logging.getLogger("nba").error("Error en %s: %s",request.url.path,type(error).__name__)
    return JSONResponse(status_code=503,content={"detail":"El servicio no pudo completar la operación. Intenta de nuevo."})


@app.get("/api/health")
def health():
    return {"estado":"listo","motor":"flujo_ortools","revision":svc.REVISION,"clientes":len(svc.DATA)}


@app.get("/api/config")
def config():
    current=svc.active()
    return {"config":current["config"] if current else svc.RETO,"config_reto":svc.RETO,
            "version_activa":current["version"] if current else None,"fecha":current["fecha"] if current else "2026-11-05",
            "meta":10241.5,"columnas":list(svc.DATA.columns),"tipos_columnas":svc.TYPES,"clientes":len(svc.DATA),
            "operadores":["==","!=","<","<=",">",">=","en","no_en","contiene"],"referencia":svc.REFERENCE}


@app.get("/api/reto")
def reto():
    return svc.public(svc.simulate(svc.RETO,"2026-11-05"))


@app.post("/api/simular")
def simulate(p:Pedido):
    return svc.public(svc.simulate(diccionario(p.config),p.fecha.isoformat()))


def filtered(run_id,q,filter_value):
    grid=svc.grid_for(run_id)
    if q: grid=grid[grid.id_cliente.str.contains(q.strip(),case=False,regex=False)]
    if filter_value in ("asignado","sin_accion"): grid=grid[grid.estado==filter_value]
    elif filter_value and filter_value!="todos":
        record=svc.load_run(run_id)
        if filter_value in record["config"]["parametros"]["canal"]["capacidad_por_corrida"]: grid=grid[grid.canal==filter_value]
        elif filter_value in [c["id"] for c in record["config"]["campanas"]]: grid=grid[(grid.campana_1==filter_value)|(grid.campana_2==filter_value)]
        else: raise ValueError("Filtro desconocido")
    return grid


@app.get("/api/parrilla/{run_id}/csv")
@app.get("/api/parrilla/{run_id}.csv")
def csv(run_id:str,metodo:Literal["optimo"]="optimo"):
    svc.load_run(run_id)
    raw=svc.STORE.read(f"corridas/{run_id}/parrilla.csv.gz")
    if raw is None: raise FileNotFoundError("La parrilla no existe")
    def chunks():
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as file:
            while part:=file.read(65536): yield part
    return StreamingResponse(chunks(),media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition":f'attachment; filename="parrilla_{run_id}.csv"',"Cache-Control":"private, no-store"})


@app.get("/api/parrilla/{run_id}/certificado")
def certificate(run_id:str):
    svc.load_run(run_id)
    raw=svc.STORE.read(f"corridas/{run_id}/certificado.json.gz")
    if raw is None: raise FileNotFoundError("El certificado no existe")
    return StreamingResponse(iter([raw]),media_type="application/gzip",
        headers={"Content-Disposition":f'attachment; filename="certificado_{run_id}.json.gz"'})


@app.get("/api/parrilla/{run_id}")
def grid(run_id:str,metodo:Literal["optimo"]="optimo",pagina:int=Query(1,ge=1),por_pagina:int=Query(30,ge=1,le=500),q:str=Query("",max_length=120),filtro:str="todos"):
    data=filtered(run_id,q,filtro);count=len(data);pages=max(1,(count+por_pagina-1)//por_pagina);pagina=min(pagina,pages)
    return {"total":count,"pagina":pagina,"paginas":pages,"filas":data.iloc[(pagina-1)*por_pagina:pagina*por_pagina].to_dict("records")}


@app.get("/api/versiones")
def list_versions():
    return {"versiones":[{k:v for k,v in item.items() if k!="config"} for item in svc.versions()],"activa":(svc.active() or {}).get("version")}


@app.post("/api/versiones")
@app.post("/api/publicar")
def save_version(p:Guardar):
    return svc.save_version(diccionario(p.config),p.fecha.isoformat(),p.nombre)


@app.get("/api/versiones/{key}")
def get_version(key:str):
    return svc.version(key)


@app.post("/api/versiones/{key}/activar")
def activate(key:str):
    item=svc.version(key)
    config=diccionario(Configuracion.model_validate(item["config"]))
    record=svc.simulate(config,item["fecha"])
    svc.STORE.write_json("activa.json",{"version":key,"corrida":record["id"],"actualizada":svc.now()})
    return {"version":key,"corrida":record["id"],"estado":"activa"}
