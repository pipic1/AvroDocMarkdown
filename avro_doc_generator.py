import avro.schema
import json
import os
import argparse
from typing import Dict, Any, List

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
            return ' | '.join([self._get_single_mermaid_type(t) for t in field_type])
        return self._get_single_mermaid_type(field_type)

    def _get_single_mermaid_type(self, type_schema: Any) -> str:
        """
        Convertit un type Avro unique en type Mermaid
        
        :param type_schema: Schéma de type Avro
        :return: Type Mermaid
        """
        if isinstance(type_schema, str):
            return type_schema
        
        if hasattr(type_schema, 'type'):
            if type_schema.type == 'record':
                return f"{type_schema.name}"
            elif type_schema.type == 'enum':
                return f"{type_schema.name}"
            elif type_schema.type == 'array':
                return f"List<{self._get_single_mermaid_type(type_schema.items)}>"
            elif type_schema.type == 'map':
                return f"Map<{self._get_single_mermaid_type(type_schema.values)}>"
        
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
                return f"Record ({type_schema.name})"
            elif type_schema.type == 'enum':
                return f"Enum ({type_schema.name})"
            elif type_schema.type == 'array':
                return f"Tableau de {self._get_single_type_name(type_schema.items)}"
            elif type_schema.type == 'map':
                return f"Map de {self._get_single_type_name(type_schema.values)}"
        
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
