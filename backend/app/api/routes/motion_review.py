"""Read-only local reference review; protected by the site's API session middleware."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router=APIRouter()
ROOT=Path(__file__).resolve().parents[4]
DIRECTORY=ROOT/'output/ballpark/team-motion-az-v1'
SWING_DIRECTORY=ROOT/'output/ballpark/perdomo-swing-v1'

def batter_reference(batter_id:int,stand:str):
    if batter_id!=672695 or stand not in ['L','R']:raise HTTPException(404,'Swing reference unavailable')
    path=SWING_DIRECTORY/f'{stand}-review.json'
    if not path.is_file():raise HTTPException(404,'Swing reference not processed')
    value=json.loads(path.read_text(encoding='utf-8'))
    if value['clip']['playerId']!=batter_id or value['clip']['stand']!=stand:raise HTTPException(404,'Swing reference identity mismatch')
    return value,path

@router.get('/batter/{batter_id}/{stand}/data')
def batter_data(batter_id:int,stand:str):
    _,path=batter_reference(batter_id,stand)
    return FileResponse(path,media_type='application/json',headers={'Cache-Control':'private, no-cache'})

@router.get('/batter/{batter_id}/{stand}/video')
def batter_video(batter_id:int,stand:str):
    value,_=batter_reference(batter_id,stand)
    path=(SWING_DIRECTORY/value['clip']['video']).resolve()
    if not path.is_relative_to(SWING_DIRECTORY.resolve()) or not path.is_file():raise HTTPException(404,'Swing video unavailable')
    return FileResponse(path,media_type='video/mp4',headers={'Cache-Control':'private, no-cache'})

def manifest():
    path=DIRECTORY/'manifest.json'
    if not path.is_file():raise HTTPException(404,'Reference batch unavailable')
    return json.loads(path.read_text(encoding='utf-8'))

def selected(pitcher_id:int):
    player=next((p for p in manifest()['players'] if p['playerId']==pitcher_id),None)
    if not player:raise HTTPException(404,'Pitcher is not in this reference batch')
    clip=next((c for c in player['clips'] if c['id']==player['selectedClipId']),None)
    if not clip:raise HTTPException(404,'No processed reference for this pitcher')
    return clip

@router.get('/index')
def index():
    data=manifest()
    return dict(version=data['version'],year=data['year'],team=data['team'],scope=data['scope'],
      players=[{k:p[k] for k in ['playerId','playerName','status','selectedClipId']} for p in data['players']])

@router.get('/{pitcher_id}/data')
def data(pitcher_id:int):
    selected(pitcher_id)
    path=DIRECTORY/f'{pitcher_id}-review.json'
    if not path.is_file():raise HTTPException(404,'Reference data unavailable')
    return FileResponse(path,media_type='application/json',headers={'Cache-Control':'private, no-cache'})

@router.get('/{pitcher_id}/quality')
def quality(pitcher_id:int):
    selected(pitcher_id)
    path=DIRECTORY/'quality.json'
    if not path.is_file():raise HTTPException(404,'Reference quality report unavailable')
    report=json.loads(path.read_text(encoding='utf-8'))
    player=next((p for p in report['players'] if p['playerId']==pitcher_id),None)
    if not player:raise HTTPException(404,'Reference quality report unavailable')
    return dict(**player,scoreDefinition=report['scoreDefinition'],denominator=report['denominator'])

@router.get('/{pitcher_id}/video')
def video(pitcher_id:int):
    clip=selected(pitcher_id)
    path=(DIRECTORY/clip['video']).resolve()
    if not path.is_relative_to(DIRECTORY.resolve()) or not path.is_file():raise HTTPException(404,'Reference video unavailable')
    return FileResponse(path,media_type='video/mp4',headers={'Cache-Control':'private, max-age=3600'})
