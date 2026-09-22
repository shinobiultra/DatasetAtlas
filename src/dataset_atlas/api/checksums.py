"""Value-based JSON exchange digest stable across browser numeric serialization."""
import hashlib
import json
import math

ALGORITHM='atlas-values-v1'

def exchange_checksum(value):
    def canonical(item):
        if item is None:return ['null']
        if isinstance(item,bool):return ['boolean',item]
        if isinstance(item,(int,float)):
            try:number=float(item)
            except OverflowError:raise ValueError('Selection exchange number exceeds browser range') from None
            if not math.isfinite(number):raise ValueError('Selection exchange requires finite numbers')
            if isinstance(item,int) and int(number)!=item:raise ValueError('Selection exchange integer exceeds exact browser range; source should represent this identifier as text')
            return ['number',(number if number else 0.0).hex()]
        if isinstance(item,str):return ['string',item]
        if isinstance(item,list):return ['array',[canonical(child) for child in item]]
        if isinstance(item,dict):return ['object',[[key,canonical(item[key])] for key in sorted(item)]]
        raise ValueError('Unsupported selection exchange value')
    encoded=json.dumps(canonical(value),ensure_ascii=True,separators=(',',':')).encode()
    return hashlib.sha256(encoded).hexdigest()
