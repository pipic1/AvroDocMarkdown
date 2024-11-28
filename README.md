# 📄AvroDocMarkdown

## Description

The Avro documentation generator is a Python tool that automatically generates detailed documentation from Avro schema files. It creates comprehensive Markdown documentation that includes:

- A Mermaid class diagram visualizing the schema structure
- Detailed descriptions of records and their fields
- Information about enumerations
- Relationships between different schema objects

## Features

- Automatic generation of Markdown documentation
- Creation of Mermaid class diagrams
- Detailed extraction of information from the Avro schema
- Support for complex types: records, enums, arrays, maps
- Documentation of fields, types, descriptions, and default values

## Prerequisites

- Python 3.8+
- Apache Avro (`avro-python3`)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-username/avro-doc-generator.git
cd avro-doc-generator
```

2. Install the dependencies:
```bash
pip install avro-python3
```

## Usage

### Command line

```bash
python avro_doc_generator.py path/to/your/schema.avsc
```

Options:
- `--output`: Specify the output directory (default: `docs`)

### Example

```bash
python avro_doc_generator.py my_schema.avsc --output documentation
```

### Programmatic usage

```python
from avro_doc_generator import AvroDocumentationGenerator

# Initialize the generator
generator = AvroDocumentationGenerator('my_schema.avsc')

# Generate the documentation
documentation = generator.generate_markdown_documentation()

# Save the documentation
generator.save_documentation(documentation)
```

## Output

The generator produces:
- An `avro_schema_doc.md` file in the output directory
- Contains a complete documentation of the Avro schema

## Internal workings

The generator recursively analyzes the Avro schema and extracts:
- The structure of records
- Enumerations
- Relationships between types
- Field descriptions

## Known limitations

- Recursion depth limited to 10 levels
- May not handle extremely complex Avro schemas

## Contribution

1. Fork the repository
2. Create a branch for your feature
3. Commit your changes
4. Create a Pull Request

## License

[MIT, Apache 2.0]

## Author

pipic1

**Note:**

- **Mermaid:** This refers to a JavaScript-based diagramming and charting tool that can be used to create various types of diagrams, including class diagrams. It's particularly useful for visualizing complex data structures like those found in Avro schemas.
- **Avro:** A data serialization system designed to be efficient, compact, and readable. It's widely used in data processing systems like Apache Kafka.
- **Markdown:** A lightweight markup language with plain text formatting syntax. It's commonly used to create readable documentation.
