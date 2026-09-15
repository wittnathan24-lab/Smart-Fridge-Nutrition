"""Deterministic portfolio fixtures, never represented as live USDA results."""
import json
import secrets
from fastapi import APIRouter
from auth import token, password_hash
from database import connection

router = APIRouter(tags=['Demo'])
RECIPES = [
 {'meal_id':'demo-1','name':'Bowl de poulet, riz & brocoli','category':'Équilibre','ingredients':[{'name':'Poulet','measure':'150 g'},{'name':'Riz cuit','measure':'180 g'},{'name':'Brocoli','measure':'150 g'}],'instructions':'1. Faites cuire le riz selon les indications du paquet.\n2. Découpez le poulet et faites-le cuire à cœur dans une poêle.\n3. Faites cuire le brocoli à la vapeur.\n4. Assemblez le bowl et assaisonnez à votre goût.','calories':520,'protein':48,'carbs':57,'fat':11},
 {'meal_id':'demo-2','name':'Salade de lentilles & tomates','category':'Végétal','ingredients':[{'name':'Lentilles cuites','measure':'200 g'},{'name':'Tomates','measure':'150 g'},{'name':"Huile d’olive",'measure':'10 g'}],'instructions':'1. Rincez les lentilles cuites.\n2. Coupez les tomates en dés.\n3. Mélangez avec l’huile et les herbes de votre choix.','calories':360,'protein':20,'carbs':44,'fat':12},
 {'meal_id':'demo-3','name':'Omelette verte & tartines','category':'Express','ingredients':[{'name':'Œufs','measure':'120 g'},{'name':'Épinards','measure':'100 g'},{'name':'Pain complet','measure':'80 g'}],'instructions':'1. Faites revenir les épinards.\n2. Battez les œufs et versez-les dans la poêle.\n3. Laissez cuire puis servez avec le pain grillé.','calories':420,'protein':27,'carbs':39,'fat':18}
]

@router.post('/auth/demo', status_code=201)
def demo():
    email = 'demo-' + secrets.token_hex(12) + '@example.invalid'
    profile = {'weight_kg':70,'height_cm':175,'age':30,'sex':'female','activity_level':'moderate','goal':'maintenance'}
    with connection() as db:
        uid = db.execute('INSERT INTO users(email,password,profile) VALUES (?,?,?)', (email,password_hash(secrets.token_urlsafe(32)),json.dumps(profile))).lastrowid
        db.executemany('INSERT INTO items(user_id,name,quantity_g) VALUES (?,?,?)', [(uid,'Poulet',300),(uid,'Riz',400),(uid,'Brocoli',250),(uid,'Tomates',300)])
    return {**token({'id':uid,'email':email}), 'demo':True}
