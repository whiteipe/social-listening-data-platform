{# Dataset único: ignora +schema por camada e usa sempre o dataset do target. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ target.schema }}
{%- endmacro %}
