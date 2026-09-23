"""Explicit native subsets require both source and selected population counts."""


def population_counts(native_count, selected_count, record_filter, expected_source_count):
    if record_filter is not None:
        if not isinstance(record_filter, dict) or set(record_filter) != {'asset_modality'} or record_filter['asset_modality'] not in {'image','audio','video'}:
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
    return record_filter is None or any(asset.modality == record_filter['asset_modality'] for asset in record.assets)
