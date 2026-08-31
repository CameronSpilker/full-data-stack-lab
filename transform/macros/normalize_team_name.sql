{#
    Reduce a school name to a joinable key.

    ESPN and Barttorvik disagree about punctuation, abbreviations, and whether
    a mascot belongs in the name: "Saint Mary's Gaels" and "St. Mary's" are the
    same program. This strips everything the two sources disagree about
    mechanically. The residue — genuine editorial differences like "UConn"
    against "Connecticut" — is what the team_name_crosswalk seed is for.
#}

{% macro normalize_team_name(column) %}
    trim(
        regexp_replace(
            regexp_replace(
                replace(
                    replace(
                        replace(lower({{ column }}), '&', ' and '),
                        '.', ''
                    ),
                    '''', ''
                ),
                '\b(saint|st)\b', 'st', 'g'
            ),
            '[^a-z0-9 ]', ' ', 'g'
        )
    )
{% endmacro %}
