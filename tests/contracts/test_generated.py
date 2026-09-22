import importlib.util
from pathlib import Path

def test_generated_types_and_schema_are_current():
    root=Path(__file__).resolve().parents[2]
    targets=[root/'schemas/atlas.schema.json',root/'apps/web/src/generated.ts']
    before=[p.read_text() for p in targets]
    spec=importlib.util.spec_from_file_location('generate',root/'scripts/generate_contracts.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.generate()
    assert [p.read_text() for p in targets]==before,'Regenerate shared contracts before committing'
