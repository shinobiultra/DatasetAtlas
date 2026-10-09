"""Explicit native subsets require both source and selected population counts."""
import re


def _class_groups(spec):
    if not isinstance(spec,dict) or set(spec)!={'field','groups','provenance'} or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',str(spec.get('field',''))):
        raise ValueError('Unsupported native class-group filter')
    groups=spec['groups']
    if not isinstance(groups,list) or not 1<=len(groups)<=32 or not isinstance(spec['provenance'],dict):
        raise ValueError('Native class-group definition exceeds its bound')
    used=set()
    for index,group in enumerate(groups):
        if not isinstance(group,dict) or set(group)!={'name','start','end'} or not isinstance(group['name'],str) or not 1<=len(group['name'])<=256:
            raise ValueError('Invalid native class-group name')
        start,end=group['start'],group['end']
        if type(start) is not int or type(end) is not int or not 0<=start<=end<=10000:
            raise ValueError('Invalid native class-group bounds')
        values=set(range(start,end+1))
        if used&values:raise ValueError('Overlapping native class groups')
        used.update(values)
    return groups


def population_counts(native_count, selected_count, record_filter, expected_source_count):
    if record_filter is not None:
        if isinstance(record_filter,dict) and set(record_filter)=={'native_class_groups'}:
            _class_groups(record_filter['native_class_groups'])
        elif not isinstance(record_filter, dict) or set(record_filter) != {'asset_modality'} or record_filter['asset_modality'] not in {'image','audio','video'}:
            raise ValueError('Unsupported native record filter')
        if type(selected_count) is not int or selected_count < 1 or type(expected_source_count) is not int or expected_source_count < selected_count:
            raise ValueError('A filtered release needs exact source and selected counts')
        if native_count != expected_source_count:
            raise ValueError('Native source count differs from the declared subset source')
        return selected_count
    if selected_count is not None and native_count != selected_count:
        raise ValueError('Source count differs from declared release population')
    return native_count


def accepts_record(record, record_filter):
    if record_filter is None:return True
    if 'native_class_groups' in record_filter:
        spec=record_filter['native_class_groups'];value=record.source.get(spec['field'])
        return type(value) is int and any(group['start']<=value<=group['end'] for group in spec['groups'])
    return any(asset.modality == record_filter['asset_modality'] for asset in record.assets)


def filter_record(record,record_filter):
    """Preserve native labels and attach the explicitly pinned author grouping."""
    if not accepts_record(record,record_filter):return False
    if record_filter and 'native_class_groups' in record_filter:
        if '_atlas_native_class_group' in record.source:raise ValueError('Source collides with reserved native class-group provenance')
        spec=record_filter['native_class_groups'];value=record.source[spec['field']]
        index,group=next((index,group) for index,group in enumerate(spec['groups']) if group['start']<=value<=group['end'])
        record.source['_atlas_native_class_group']={'id':index,'name':group['name'],'native_label':value,
            'inclusive_range':[group['start'],group['end']],'source_field':spec['field'],'provenance':spec['provenance']}
    return True
