{#
    Use custom schemas literally instead of prefixing them with the target
    schema. dbt's default would name the marts `main_marts`; this makes them
    `marts`, so the warehouse reads as raw / staging / intermediate / marts
    and the Evidence queries reference the names the README documents.

    This is safe here because the warehouse is a single-developer DuckDB file.
    On a shared warehouse the default prefixing is what keeps two people from
    building over each other, and this macro should not be copied across.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}
