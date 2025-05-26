import avro.schema
import json
import os
import argparse
from typing import Dict, Any, List
import re

class AvroDocumentationGenerator:
    def __init__(self, avro_file_path: str, output_dir: str = 'docs'):
        """
        Initialise le générateur de documentation Avro

        :param avro_file_path: Chemin vers le fichier de schéma Avro
        :param output_dir: Répertoire de sortie pour la documentation
        """
        self.avro_file_path = avro_file_path
        self.output_dir = output_dir
        self.schema = avro.schema.parse(open(avro_file_path, 'rb').read())
        
        # Dictionnaires pour stocker les sous-objets et enums
        self.records = {}
        self.enums = {}
        self.processed_types = set()

    def generate_mermaid_class_diagram(self) -> str:
        """
        Génère un diagramme de classe Mermaid représentant les relations entre objets
        
        :return: Diagramme de classe Mermaid
        """
        mermaid_diagram = "```mermaid\nclassDiagram\n"
        
        # Ajout des enums
        for enum_name, enum_schema in self.enums.items():
            mermaid_diagram += f"    class {enum_name} {{\n"
            mermaid_diagram += "        <<enumeration>>\n"
            for symbol in enum_schema.symbols:
                mermaid_diagram += f"        {symbol}\n"
            mermaid_diagram += "    }\n"
        
        # Ajout des records
        for record_name, record_schema in self.records.items():
            mermaid_diagram += f"    class {record_name} {{\n"
            for field in record_schema.fields:
                field_type = self._get_mermaid_field_type(field.type)
                mermaid_diagram += f"        {field_type} {field.name}\n"
            mermaid_diagram += "    }\n"
        
        # Ajout des relations principales
        mermaid_diagram += self._generate_class_relations()
        
        mermaid_diagram += "\n```\n"
        return mermaid_diagram

    def _generate_class_relations(self) -> str:
        """
        Génère les relations entre classes et énumérations avec une protection contre la récursion infinie

        :return: Chaîne de relations Mermaid
        """
        relations = ""
        processed_relations = set()
        
        def process_type_relations(type_schema, parent_name=None, depth=0):
            nonlocal relations
            
            # Protection contre la récursion profonde
            if depth > 10:
                return
            
            # Gestion des types unions
            if isinstance(type_schema, list):
                for sub_type in type_schema:
                    process_type_relations(sub_type, parent_name, depth + 1)
                return
            
            if not hasattr(type_schema, 'type'):
                return
            
            if type_schema.type == 'record':
                # Relations pour les champs qui sont des sous-records ou des enums
                for field in type_schema.fields:
                    # Vérifier si le type du champ est un record ou un enum
                    if hasattr(field.type, 'type'):
                        if field.type.type == 'record' and hasattr(field.type, 'name'):
                            # Relation avec un sous-record
                            relation_key = (type_schema.name, field.type.name, field.name, 'record')
                            if relation_key not in processed_relations:
                                relations += f"    {type_schema.name} --> {field.type.name} : {field.name}\n"
                                processed_relations.add(relation_key)
                        
                        elif field.type.type == 'enum' and hasattr(field.type, 'name'):
                            # Relation avec une énumération
                            relation_key = (type_schema.name, field.type.name, field.name, 'enum')
                            if relation_key not in processed_relations:
                                relations += f"    {type_schema.name} ..> {field.type.name} : {field.name}\n"
                                processed_relations.add(relation_key)
                        
                        # Analyse récursive des sous-types
                        process_type_relations(field.type, type_schema.name, depth + 1)
                    
                    # Gestion des types tableau
                    elif isinstance(field.type, list):
                        for sub_type in field.type:
                            if hasattr(sub_type, 'type'):
                                if sub_type.type == 'record':
                                    # Relation avec un record dans un tableau
                                    relation_key = (type_schema.name, sub_type.name, field.name, 'record_list')
                                    if relation_key not in processed_relations:
                                        relations += f"    {type_schema.name} --> {sub_type.name} : {field.name}\n"
                                        processed_relations.add(relation_key)
                                
                                elif sub_type.type == 'enum':
                                    # Relation avec une énumération dans un tableau
                                    relation_key = (type_schema.name, sub_type.name, field.name, 'enum_list')
                                    if relation_key not in processed_relations:
                                        relations += f"    {type_schema.name} ..> {sub_type.name} : {field.name}\n"
                                        processed_relations.add(relation_key)
            
            elif type_schema.type == 'array':
                # Relations pour les tableaux de records ou d'enums
                if hasattr(type_schema.items, 'type'):
                    if type_schema.items.type == 'record' and hasattr(type_schema.items, 'name'):
                        # Relation avec un record dans un tableau
                        if parent_name:
                            relation_key = (parent_name, type_schema.items.name, 'array_record')
                            if relation_key not in processed_relations:
                                relations += f"    {parent_name} --> {type_schema.items.name} : {type_schema.items.name} liste\n"
                                processed_relations.add(relation_key)
                    
                    elif type_schema.items.type == 'enum' and hasattr(type_schema.items, 'name'):
                        # Relation avec une énumération dans un tableau
                        if parent_name:
                            relation_key = (parent_name, type_schema.items.name, 'array_enum')
                            if relation_key not in processed_relations:
                                relations += f"    {parent_name} ..> {type_schema.items.name} : {type_schema.items.name} liste\n"
                                processed_relations.add(relation_key)
                    
                    # Analyse récursive des éléments du tableau
                    process_type_relations(type_schema.items, parent_name, depth + 1)

        # Commencer par le schéma principal
        process_type_relations(self.schema)
        
        return relations
    
    def _get_mermaid_field_type(self, field_type: Any) -> str:
        """
        Convertit un type Avro en type compatible Mermaid
        
        :param field_type: Type du champ Avro
        :return: Type pour le diagramme Mermaid
        """
        if isinstance(field_type, list):
            # Check for nullable type: union of "null" and one other type
            if len(field_type) == 2 and "null" in field_type:
                other_type = [t for t in field_type if t != "null"][0]
                return f"{self._get_single_mermaid_type(other_type)}?"
            else:
                # Default handling for other unions
                return ' | '.join([self._get_single_mermaid_type(t) for t in field_type])
        return self._get_single_mermaid_type(field_type)

    def _get_single_mermaid_type(self, type_schema: Any) -> str:
        """
        Convertit un type Avro unique en type Mermaid
        
        :param type_schema: Schéma de type Avro
        :return: Type Mermaid
        """
        if isinstance(type_schema, str):
            # Primitive types like "string", "int", "boolean"
            return type_schema
        
        if hasattr(type_schema, 'type'):
            if type_schema.type == 'record':
                return f"{type_schema.name}"
            elif type_schema.type == 'enum':
                return f"{type_schema.name}"
            elif type_schema.type == 'array':
                # Use _get_mermaid_field_type for items to handle nested nullability (e.g., List<MyType?>)
                return f"List<{self._get_mermaid_field_type(type_schema.items)}>"
            elif type_schema.type == 'map':
                # Use _get_mermaid_field_type for values to handle nested nullability
                return f"Map<{self._get_mermaid_field_type(type_schema.values)}>"
        
        # Fallback for any other complex type structure not explicitly handled
        return str(type_schema)


    def generate_markdown_documentation(self) -> str:
        """
        Génère une documentation Markdown à partir du schéma Avro

        :return: Contenu de la documentation au format Markdown
        """
        # Réinitialise les dictionnaires de records et enums
        self.records = {}
        self.enums = {}
        self.processed_types = set()

        # Analyse récursive pour extraire les sous-objets et enums
        self._extract_nested_types(self.schema)

        # Génération de la documentation principale
        doc = f"# Documentation du Schéma Avro\n\n"

        # Ajouter le diagramme de classe Mermaid
        doc += "## Structure du Schéma\n\n"
        doc += self.generate_mermaid_class_diagram()
        doc += "\n"
        
        # Informations du schéma principal
        doc += f"## Schéma Principal: {self.schema.name}\n"
        doc += f"- **Namespace**: {self.schema.namespace}\n"
        doc += f"- **Type**: {self.schema.type}\n"
        
        if self.schema.doc:
            doc += f"- **Description**: {self.schema.doc}\n\n"

        # Structure des champs principaux
        doc += "### Structure des Champs\n\n"
        doc += self._parse_record_fields(self.schema)

        # Sous-objets Records
        if self.records:
            doc += "\n## Définition Détaillée des Sous-Objets\n\n"
            for name, record_schema in self.records.items():
                doc += f"### Sous-Objet: {name}\n\n"
                
                # Description du sous-objet
                if record_schema.doc:
                    doc += f"**Description**: {record_schema.doc}\n\n"
                
                # Champs du sous-objet
                doc += "#### Champs\n\n"
                doc += self._parse_record_fields(record_schema, is_detailed=True)

        # Énumérations
        if self.enums:
            doc += "\n## Énumérations\n\n"
            for name, enum_schema in self.enums.items():
                doc += f"### Énumération: {name}\n\n"
                
                # Description de l'énumération
                if enum_schema.doc:
                    doc += f"**Description**: {enum_schema.doc}\n\n"
                
                # Valeurs de l'énumération
                doc += "**Valeurs possibles**:\n"
                doc += "\n".join([f"- `{symbol}`" for symbol in enum_schema.symbols])
                doc += "\n\n"
        
        # Section Conseils et Bonnes Pratiques
        doc += "\n## Conseils et Bonnes Pratiques\n\n"
        advice_list = self._detect_bad_practices()
        if advice_list:
            for advice in advice_list:
                doc += f"- {advice}\n"
            doc += "\n"
        else:
            doc += "Aucune mauvaise pratique notable détectée.\n\n"

        return doc

    def _extract_nested_types(self, schema: avro.schema.Schema):
        """
        Extrait récursivement les sous-objets records et enums

        :param schema: Schéma Avro à analyser
        """
        def _extract_from_type(type_schema):
            # Vérification pour éviter la récursion infinie
            if id(type_schema) in self.processed_types:
                return
            
            self.processed_types.add(id(type_schema))

            # Extraction pour un type donné
            if isinstance(type_schema, list):
                # Gère les types union
                for sub_type in type_schema:
                    _extract_from_type(sub_type)
                return

            if hasattr(type_schema, 'type'):
                if type_schema.type == 'record':
                    if hasattr(type_schema, 'name') and type_schema.name not in self.records:
                        self.records[type_schema.name] = type_schema
                    
                    # Analyse récursive des champs du record
                    for field in type_schema.fields:
                        _extract_from_type(field.type)
                
                elif type_schema.type == 'enum':
                    if hasattr(type_schema, 'name'):
                        self.enums[type_schema.name] = type_schema
                
                elif type_schema.type == 'array':
                    # Pour les tableaux, analyse le type des éléments
                    _extract_from_type(type_schema.items)
                
                elif type_schema.type == 'map':
                    # Pour les maps, analyse le type des valeurs
                    _extract_from_type(type_schema.values)

        # Analyse de chaque champ du schéma principal
        if schema.type == 'record':
            for field in schema.fields:
                _extract_from_type(field.type)

    def _parse_record_fields(self, schema: avro.schema.Schema, indent: int = 0, is_detailed: bool = False) -> str:
        """
        Analyse les champs d'un schéma Avro

        :param schema: Schéma Avro à analyser
        :param indent: Niveau d'indentation pour la mise en forme
        :param is_detailed: Indicateur pour un affichage détaillé
        :return: Documentation Markdown des champs
        """
        doc = ""
        if schema.type == 'record':
            for field in schema.fields:
                # Nom du champ
                doc += f"**{field.name}**\n"
                
                # Type du champ
                field_type = self._get_field_type(field.type)
                doc += f"- **Type**: {field_type}\n"
                
                # Documentation du champ si disponible
                if field.doc:
                    doc += f"- **Description**: {field.doc}\n"
                
                # Gestion des valeurs par défaut
                try:
                    if 'default' in field.__dict__:
                        default_value = field.default
                        doc += f"- **Valeur par défaut**: `{default_value}`\n"
                except Exception:
                    # Si la récupération de la valeur par défaut échoue
                    doc += "- **Valeur par défaut**: Non spécifiée\n"
                
                # Pour un affichage détaillé, ajouter plus d'informations
                if is_detailed:
                    # Vérifier le type
                    if isinstance(field.type, dict) and field.type.get('type') == 'record' and 'name' in field.type:
                        doc += f"- **Sous-Type**: [Voir définition de {field.type['name']}](#sous-objet-{field.type['name'].lower()})\n"
                    elif isinstance(field.type, dict) and field.type.get('type') == 'enum' and 'name' in field.type:
                        doc += f"- **Énumération**: [Voir définition de {field.type['name']}](#énumération-{field.type['name'].lower()})\n"
                
                doc += "\n"
        
        return doc

    def _get_field_type(self, field_type: Any) -> str:
        """
        Récupère le type lisible d'un champ Avro

        :param field_type: Type du champ Avro
        :return: Type sous forme de chaîne lisible
        """
        # Gestion des types union
        if isinstance(field_type, list):
            # Check for nullable type: union of "null" and one other type
            if len(field_type) == 2 and "null" in field_type:
                other_type = [t for t in field_type if t != "null"][0]
                return f"{self._get_single_type_name(other_type)} (nullable)"
            else:
                # Default handling for other unions
                return ' ou '.join([self._get_single_type_name(t) for t in field_type])
        
        # Gestion des types simples et complexes
        return self._get_single_type_name(field_type)

    def _get_single_type_name(self, type_schema: Any) -> str:
        """
        Récupère le nom d'un type unique

        :param type_schema: Schéma de type Avro
        :return: Nom du type lisible
        """
        if isinstance(type_schema, str):
            return type_schema
        
        if hasattr(type_schema, 'type'):
            if type_schema.type == 'record':
                return f"record<{type_schema.name}>"
            elif type_schema.type == 'enum':
                return f"enum<{type_schema.name}>"
            elif type_schema.type == 'array':
                # Use _get_field_type for items to handle nested nullability correctly
                return f"array<{self._get_field_type(type_schema.items)}>"
            elif type_schema.type == 'map':
                # Use _get_field_type for values to handle nested nullability correctly
                return f"map<{self._get_field_type(type_schema.values)}>"
        
        return str(type_schema)

    def save_documentation(self, content: str):
        """
        Sauvegarde la documentation générée dans un fichier

        :param content: Contenu de la documentation
        """
        os.makedirs(self.output_dir, exist_ok=True)
        output_file = os.path.join(self.output_dir, 'avro_schema_doc.md')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Documentation générée : {output_file}")

    def _detect_bad_practices(self) -> List[str]:
        """
        Analyse le schéma Avro chargé et identifie les mauvaises pratiques potentielles.
        Retourne une liste de chaînes descriptives des problèmes trouvés.
        """
        bad_practices: List[str] = []

        # S'assurer que _extract_nested_types a été appelé
        if not self.records and not self.enums and self.schema.type == 'record':
            # Appel préliminaire si les structures ne sont pas remplies.
            # Cela est important si _detect_bad_practices est appelé indépendamment.
            self._extract_nested_types(self.schema)

        # 1. Documentation Manquante
        all_records_to_check: Dict[str, Any] = {}
        if self.schema.type == 'record':
            all_records_to_check[self.schema.name] = self.schema
        all_records_to_check.update(self.records)

        # Documentation du schéma principal
        if self.schema.type == 'record' and not self.schema.props.get('doc'):
            bad_practices.append(f"Le schéma principal '{self.schema.name}' n'a pas de documentation ('doc').")
        elif self.schema.type != 'record' and not self.schema.props.get('doc'): # Pour les schémas non-record (ex: juste un type array ou map en root)
             # Tenter de trouver un nom, sinon utiliser le type.
            schema_name = getattr(self.schema, 'name', self.schema.type)
            bad_practices.append(f"Le schéma principal '{schema_name}' n'a pas de documentation ('doc').")


        # Documentation des records et de leurs champs
        for record_name, record_schema in all_records_to_check.items():
            if not record_schema.props.get('doc'):
                bad_practices.append(f"Le record '{record_name}' n'a pas de documentation.")
            
            for field in record_schema.fields:
                if not field.props.get('doc'):
                    bad_practices.append(f"Le champ '{field.name}' dans le record '{record_name}' n'a pas de documentation.")

        # Documentation des enums
        for enum_name, enum_schema in self.enums.items():
            if not enum_schema.props.get('doc'):
                bad_practices.append(f"L'enum '{enum_name}' n'a pas de documentation.")

        # 2. Noms Génériques
        GENERIC_RECORD_NAMES = {"Record", "NewRecord", "MyRecord", "Schema", "AvroSchema", "DataStructure"}
        GENERIC_FIELD_NAMES = {"field", "data", "value", "item", "entry", "key", "type", "name", "content", "payload", "details"}
        GENERIC_ENUM_NAMES = {"Enum", "MyEnum", "EnumType", "Option"}

        # Noms génériques pour les records
        for record_name in all_records_to_check.keys():
            if record_name in GENERIC_RECORD_NAMES:
                bad_practices.append(f"Le record '{record_name}' a un nom générique.")

        # Noms génériques pour les champs
        for record_name, record_schema in all_records_to_check.items():
            for field in record_schema.fields:
                if field.name in GENERIC_FIELD_NAMES:
                    bad_practices.append(f"Le champ '{field.name}' dans le record '{record_name}' a un nom générique.")
        
        # Noms génériques pour les enums
        for enum_name in self.enums.keys():
            if enum_name in GENERIC_ENUM_NAMES:
                bad_practices.append(f"L'enum '{enum_name}' a un nom générique.")
        
        # 3. Conventions des Symboles d'Enum
        for enum_name, enum_schema in self.enums.items():
            for symbol in enum_schema.symbols:
                if len(symbol) < 3:
                    bad_practices.append(f"Le symbole '{symbol}' dans l'enum '{enum_name}' est trop court (moins de 3 caractères).")
                if not re.match(r"^[A-Z0-9_]+$", symbol):
                    bad_practices.append(f"Le symbole '{symbol}' dans l'enum '{enum_name}' n'est pas en UPPER_SNAKE_CASE (ex: MY_SYMBOL).")

        # 4. Valeurs par Défaut pour les Champs Union
        for record_name, record_schema in all_records_to_check.items():
            for field in record_schema.fields:
                # field.type est un avro.schema.Schema object
                # Si c'est une union, field.type sera un avro.schema.UnionSchema
                if isinstance(field.type, avro.schema.UnionSchema):
                    if hasattr(field, 'has_default') and field.has_default:
                        # La valeur par défaut doit correspondre au premier type de l'union.
                        first_type_in_union = field.type.schemas[0]
                        
                        # Convertir le nom du type avro.schema en string simple
                        first_type_name = None
                        if isinstance(first_type_in_union, avro.schema.PrimitiveSchema):
                            first_type_name = first_type_in_union.type # e.g., "null", "string"
                        elif isinstance(first_type_in_union, avro.schema.NamedSchema):
                             first_type_name = first_type_in_union.name # e.g., "MyRecord"
                        else: # Pour les types complexes non nommés comme array, map
                            first_type_name = first_type_in_union.type


                        # Cas 1: La valeur par défaut est None (null JSON), mais le premier type n'est pas "null"
                        if field.default is None or field.default == avro.schema.NULL: # avro.schema.NULL est la représentation interne pour un défaut JSON null
                            if first_type_name != "null":
                                bad_practices.append(
                                    f"Le champ '{field.name}' dans le record '{record_name}' est une union avec une valeur par défaut 'null', "
                                    f"mais son premier type n'est pas 'null' (il est '{first_type_name}'). "
                                    "La valeur par défaut doit correspondre au premier type de l'union."
                                )
                        # Cas 2 (moins direct, mais important): Le premier type est 'null', mais la valeur par défaut n'est pas None/avro.schema.NULL
                        # Ceci est généralement une erreur de schéma car une valeur non-nulle ne peut pas être assignée à un type 'null'.
                        # L'analyseur avro.schema.parse devrait normalement attraper ça, mais une vérification peut être utile.
                        elif first_type_name == "null" and field.default is not None and field.default != avro.schema.NULL:
                             bad_practices.append(
                                    f"Le champ '{field.name}' dans le record '{record_name}' est une union dont le premier type est 'null', "
                                    f"mais sa valeur par défaut ('{field.default}') n'est pas 'null'. "
                                    "Cela contredit la règle selon laquelle la valeur par défaut doit correspondre au premier type."
                                )
                        # Cas 3: Le premier type n'est pas 'null', et la valeur par défaut n'est pas 'null'.
                        # Il faut vérifier que la valeur par défaut est valide pour ce premier type.
                        # Cette validation est complexe et généralement gérée par l'analyseur Avro.
                        # Pour cette fonction, nous nous concentrons sur la règle "null" en premier.
                        # Cependant, si le premier type n'est pas 'null' et qu'une valeur par défaut est fournie,
                        # on peut au moins mentionner que 'null' devrait être le premier type si l'intention est l'optionnalité.
                        elif first_type_name != "null" and (field.default is not None and field.default != avro.schema.NULL) :
                             # Check if the default value is compatible with the first_type_name
                             # This is a more subtle point: Avro allows default for non-null first type if it matches.
                             # But the spirit of ["null", "X"] with default is usually to make X optional.
                             # If first_type_name is not "null", but a default is provided, it implies the field is not truly "optional" in the common sense.
                             # For now, we'll stick to the problem description's focus.
                             # The prompt asks to flag if "null" is not the first type when a default is present.
                             # This implicitly covers the case where default is None and first type is not "null".
                             # And if default is something else, and first type is not "null", it's valid Avro,
                             # but might be against a "best practice" if nullability was the goal.
                             # The most direct interpretation of the request is: "If a field is a union with a default, and 'null' is not its first type"
                             bad_practices.append(
                                 f"Le champ '{field.name}' dans le record '{record_name}' est une union avec une valeur par défaut. "
                                 f"Pour indiquer clairement l'optionnalité, 'null' devrait être le premier type dans l'union. Le premier type actuel est '{first_type_name}'."
                             )


        return bad_practices

def main():
    parser = argparse.ArgumentParser(description='Générateur de documentation Avro')
    parser.add_argument('schema_file', help='Chemin vers le fichier de schéma Avro')
    parser.add_argument('--output', default='docs', help='Répertoire de sortie pour la documentation')
    
    args = parser.parse_args()

    try:
        generator = AvroDocumentationGenerator(args.schema_file, args.output)
        documentation = generator.generate_markdown_documentation()
        generator.save_documentation(documentation)
    except Exception as e:
        print(f"Erreur lors de la génération de la documentation : {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == '__main__':
    main()
