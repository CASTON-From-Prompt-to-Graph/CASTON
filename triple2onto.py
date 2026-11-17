import pandas as pd
import types
from owlready2 import get_ontology, owl, rdfs, Thing, ObjectProperty,  ThingClass

from rdflib import Graph
import os

def clean_ns(file_ns, ns, file):
    g = Graph()
    g.parse(file_ns, format="ntriples")  # parsing ntriples

    # bind the namespace prefix 
    g.bind("caston", ns)
    
    g.bind("owl", "http://www.w3.org/2002/07/owl#")
    g.bind("rdfs", "http://www.w3.org/2000/01/rdf-schema#")
    g.bind("skos", "http://www.w3.org/2004/02/skos/core#")
    #g.bind("vaem", "http://www.linkedmodel.org/schema/vaem#")

    # Step 4: Serialize to Turtle with the correct prefix
    g.serialize(destination=file, format="ntriples")
    g.serialize(destination=file.replace(".nt", ".ttl"), format="turtle")
    g.serialize(destination=file.replace(".nt", ".jsonld"), format="json-ld")

    print("Ontology saved with proper prefixes")


# Load CSV file
file_path = "seed_onto_v5_v2.7_ordered_normalized_dedup.csv"  # replace with your path
df = pd.read_csv(file_path)

file_path = "seed_onto_v5_class_annotation.csv"  # replace with your path
df_concept_annotation = pd.read_csv(file_path)

file_path = "seed_onto_v5_property_annotation.csv"  # replace with your path
df_property_annotation = pd.read_csv(file_path)

# Create ontology
onto = get_ontology("http://inmost-research.org/ontologies/caston#")


# Import an property http://www.linkedmodel.org/schema/vaem#rationale
#vaem  = get_ontology("http://www.linkedmodel.org/schema/vaem").load()

# Import an property http://www.w3.org/2004/02/skos/core#scopeNote
skos  = get_ontology("http://www.w3.org/2004/02/skos/core").load()

#onto.imported_ontologies.append(vaem)
#onto.imported_ontologies.append(skos)

#Get the annotation property vaem:rationale
#rationale = vaem.search_one(iri="*#rationale")
#assert rationale is not None, "Couldn't find vaem:rationale after loading VAEM!"

#Get the annotation property skos:scopeNote
scope_note = skos.search_one(iri="*#scopeNote")
assert scope_note is not None, "Couldn't find skos:scopeNote after loading SKOS!"

altLabel = skos.search_one(iri="*#altLabel")
assert altLabel is not None, "Couldn't find skos:altLabel after loading SKOS!"

with onto:
  
    # Dictionaries to store created classes, individuals and properties
    entities = {}
    properties = {}


    #https://owlready2.readthedocs.io/en/v0.49/class.html#creating-classes-dynamically
    def get_or_create_entity(name):

        if str(name) in ["none", ""]:
            return None        

        """Return existing entity or create new one"""
        if name not in entities:
            entities[name] = types.new_class(name, (Thing,))

            #print(f"processing entity: {name}")

            if name in df_concept_annotation['name'].values:
                #handle the documentation 
                entities[name].label.en.append(df_concept_annotation[df_concept_annotation['name'] == name]['label'].values[0])
                rdfs.comment[entities[name]].append(str(df_concept_annotation[df_concept_annotation['name'] == name]['definition'].values[0]))     

                if not pd.isna(df_concept_annotation[df_concept_annotation['name'] == name]['altLabel1'].values[0]):
                   altLabel[entities[name]].append(str(df_concept_annotation[df_concept_annotation['name'] == name]['altLabel1'].values[0]))

                if not pd.isna(df_concept_annotation[df_concept_annotation['name'] == name]['altLabel2'].values[0]):
                   altLabel[entities[name]].append(str(df_concept_annotation[df_concept_annotation['name'] == name]['altLabel2'].values[0]))

                if not pd.isna(df_concept_annotation[df_concept_annotation['name'] == name]['altLabel3'].values[0]):
                   altLabel[entities[name]].append(str(df_concept_annotation[df_concept_annotation['name'] == name]['altLabel3'].values[0]))

                #if not pd.isna(df_concept_annotation[df_concept_annotation['name'] == name]['rationale'].values[0]):                     
                #     rationale[entities[name]].append(str(df_concept_annotation[df_concept_annotation['name'] == name]['rationale'].values[0]))

                if not pd.isna(df_concept_annotation[df_concept_annotation['name'] == name]['scope'].values[0]):
                     scope_note[entities[name]].append(str(df_concept_annotation[df_concept_annotation['name'] == name]['scope'].values[0]))


        return entities[name]

    #Define function to get or create property
    def get_or_create_property(name):
           
        if str(name) in ["none", ""]:
            return None
           
        """Return existing property or create new one"""
        if name not in properties:
            properties[name] = types.new_class(name, (ObjectProperty,))

            #print(f"processing property: {name}")

            if name in df_property_annotation['name'].values:
                
                #handle the documentation 
                properties[name].label.en.append(df_property_annotation[df_property_annotation['name'] == name]['label'].values[0])
                properties[name].comment.en.append(df_property_annotation[df_property_annotation['name'] == name]['definition'].values[0])     

                if not pd.isna(df_property_annotation[df_property_annotation['name'] == name]['altLabel'].values[0]):
                   properties[name].label.en.append(df_property_annotation[df_property_annotation['name'] == name]['altLabel'].values[0])            
                      
        return properties[name]
    
    # Process each triple
    for _, row in df.iterrows():

        print(f"processing triple: {row['subject']}, {row['predicate']}, {row['object']}")

        subj_cls = get_or_create_entity(row["subject"])   
        obj_cls = get_or_create_entity(row["object"])
                     
        # subclass-superclass relation
        if row["predicate"] == "isa":        

            if obj_cls not in subj_cls.is_a:
                subj_cls.is_a.append(obj_cls)   
                #remove isa relation to Thing if exists
                if Thing in subj_cls.is_a:
                    subj_cls.is_a.remove(Thing)

        # object property relation
        else:                            
            prop = get_or_create_property(row["predicate"])
            setattr(subj_cls, prop.name, obj_cls)

    # add subproperty relation for the properties in the property annotation file
    for _, row in df_property_annotation.iterrows():
        prop = get_or_create_property(row["name"])
        if not pd.isna(row['subproperty_of']):
            parent_prop = get_or_create_property(row['subproperty_of'])
            if parent_prop not in prop.is_a:
                prop.is_a.append(parent_prop)   


# Run reasoner to infer new knowledge

# Save ontology
onto.save(file="CastOnto.owl", format="rdfxml")
print("Ontology saved as ontology file in RDF/XML")

# Clean the namespace in the saved ontology file
onto.save(file="CastOnto_ns.nt", format="ntriples")
clean_ns("CastOnto_ns.nt", "http://inmost.org/ontologies/caston#", "CastOnto.nt")
#remove the CastOnto_ns.nt file
os.remove("CastOnto_ns.nt")
print("Ontology saved as ontology file in Turtle formats")
print("and namespace cleaned and ontology saved with proper prefixes")