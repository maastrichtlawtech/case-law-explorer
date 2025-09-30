from rdflib import Graph, Literal
from pyoxigraph import RdfFormat, parse, pyoxigraph
from collections import defaultdict

turtle_head = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sesame: <http://www.openrdf.org/schema/sesame#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix fn: <http://www.w3.org/2005/xpath-functions#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix dc: <http://purl.org/dc/elements/1.1/> .
@prefix hint: <http://www.bigdata.com/queryHints#> .
@prefix bd: <http://www.bigdata.com/rdf#> .
@prefix bds: <http://www.bigdata.com/rdf/search#> .
"""

def parse_turtle_chunk_1(buffer):
    g = Graph(store="Oxigraph")
    g.parse(data=turtle_head+buffer, format="ox-turtle")

    subject = None
    predicates = {}

    for s, p, o in g:
        subj = str(s)
        if subject is None:
            subject = subj.value

        pred = str(p)
        if isinstance(o, Literal):
            obj = str(o.value)
        else:
            obj = str(o)

        predicates.setdefault(pred, []).append(obj)

    return subject, predicates

def parse_turtle_chunk(buffer):
    parsed = parse(input=turtle_head+buffer, format=RdfFormat.TURTLE,)
    
    subject = None
    predicates = {}

    for s, p, o, _ in parsed:
        subj = str(s.value)
        if subject is None:
            subject = subj
        
        pred = p.value
        obj = o.value

        predicates.setdefault(pred, []).append(obj)

    return subject, predicates

def parse_turtle_triples(buffer):
    parsed = parse(input=turtle_head+buffer, format=RdfFormat.TURTLE,)
    
    for s, p, o, _ in parsed:
        subj = str(s.value)        
        pred = p.value
        obj = o.value

        yield subj, pred, obj