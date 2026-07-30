import yaml
import os
import sys

class SchemaValidator:
    def __init__(self, schema_path):
        self.schema_path = schema_path
        with open(schema_path, 'r') as f:
            self.schema = yaml.safe_load(f)
        self.known_ids = set()
        self.known_names = set()

    def validate_object(self, obj_data):
        # 1. Field wajib dasar
        base_required = ['id', 'name', 'category', 'version', 'status']
        for field in base_required:
            if field not in obj_data:
                return False, f"Missing required base field: {field}"

        # 2. Duplicate ID/Name
        if obj_data['id'] in self.known_ids:
            return False, f"Duplicate ID: {obj_data['id']}"
        if obj_data['name'] in self.known_names:
            return False, f"Duplicate Name: {obj_data['name']}"

        # 3. Category Enum
        valid_categories = self.schema['base_fields']['category'].replace('enum [', '').replace(']', '').split(', ')
        if obj_data['category'] not in valid_categories:
            return False, f"Invalid category: {obj_data['category']}"

        # 4. Status Enum
        valid_status = self.schema['base_fields']['status'].replace('enum [', '').replace(']', '').split(', ')
        if obj_data['status'] not in valid_status:
            return False, f"Invalid status: {obj_data['status']}"

        # 5. Object specific required fields
        category = obj_data['category']
        obj_required = self.schema['objects'][category].get('required', [])
        for field in obj_required:
            if field not in obj_data:
                return False, f"Missing required {category} field: {field}"

        self.known_ids.add(obj_data['id'])
        self.known_names.add(obj_data['name'])
        return True, "Valid"

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 schema_validator.py <schema_path> <object_path>")
        sys.exit(1)
    
    validator = SchemaValidator(sys.argv[1])
    with open(sys.argv[2], 'r') as f:
        data = yaml.safe_load(f)
    
    success, msg = validator.validate_object(data)
    print(msg)
    sys.exit(0 if success else 1)
