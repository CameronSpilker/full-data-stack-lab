{#
    Write every model to the schema its folder declares, rather than dbt's
    default of prefixing the target schema. The warehouse is a local DuckDB
    file with one consumer, so `marts.mart_team_season` reads better than
    `main_marts.mart_team_season` — and the Evidence queries are written
    against these names.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
