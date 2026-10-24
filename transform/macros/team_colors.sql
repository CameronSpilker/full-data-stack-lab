{#
    Choosing two teams' colours so they can be told apart.

    A page that sets two teams against each other (a matchup, a head-to-head
    bar) draws each in its own colour, and two schools often share one: BYU
    and Michigan are both navy. These macros pick, for a pair, each side's
    primary colour where the two differ enough, and otherwise switch one side
    to its secondary colour, read from its logo. The marts do it so every
    page that draws the pair agrees about it.

    Colours are six hex digits with no leading "#", as the warehouse stores
    them. The distance is the "redmean" weighting of RGB, which tracks how
    different two colours look far better than plain RGB distance and needs
    nothing but arithmetic. 0 is identical; 765 is black against white.
#}

{% macro hex_channel(color, position) -%}
    ('0x' || substr({{ color }}, {{ position }}, 2))::integer
{%- endmacro %}

{% macro color_distance(a, b) -%}
    sqrt(
        (2 + ({{ hex_channel(a, 1) }} + {{ hex_channel(b, 1) }}) / 512.0)
            * power({{ hex_channel(a, 1) }} - {{ hex_channel(b, 1) }}, 2)
        + 4 * power({{ hex_channel(a, 3) }} - {{ hex_channel(b, 3) }}, 2)
        + (2 + (510 - {{ hex_channel(a, 1) }} - {{ hex_channel(b, 1) }}) / 512.0)
            * power({{ hex_channel(a, 5) }} - {{ hex_channel(b, 5) }}, 2)
    )
{%- endmacro %}

{#
    Below this distance two colours read as one at the size of a bar. Set so
    that BYU's royal blue and Michigan's navy count as the same, which is the
    pair a reader would confuse.
#}
{% macro distinct_color_threshold() -%}200{%- endmacro %}

{#
    Each side's colour for a pair, in order of preference: both primaries;
    the first side's primary against the second's secondary; the first's
    secondary against the second's primary. If none of those differ enough,
    both keep their primaries and the page's own fallback decides.
#}
{% macro pair_color(side, a_primary, a_secondary, b_primary, b_secondary) -%}
    {%- set far = distinct_color_threshold() -%}
    case
        when {{ a_primary }} is null or {{ b_primary }} is null
            then {{ a_primary if side == 'a' else b_primary }}
        when {{ color_distance(a_primary, b_primary) }} >= {{ far }}
            then {{ a_primary if side == 'a' else b_primary }}
        when {{ b_secondary }} is not null
            and {{ color_distance(a_primary, b_secondary) }} >= {{ far }}
            then {{ a_primary if side == 'a' else b_secondary }}
        when {{ a_secondary }} is not null
            and {{ color_distance(a_secondary, b_primary) }} >= {{ far }}
            then {{ a_secondary if side == 'a' else b_primary }}
        else {{ a_primary if side == 'a' else b_primary }}
    end
{%- endmacro %}
