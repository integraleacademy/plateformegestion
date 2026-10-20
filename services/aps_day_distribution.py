"""Choose APS day lengths without scattering the ordered UVs across a day."""

from math import gcd


def grouped_day_minutes(modules, capacities, preferred_minutes, standard_minutes=420):
    """Prefer at most two UVs, allowing the fewest three-UV days if necessary.

    Sequence order and every teaching minute are retained. Among distributions
    with equally few exceptions, prefer fewer overtime minutes, then the existing
    daily rhythm. All originally active dates remain active, including the last.
    """
    if len(capacities) != len(preferred_minutes):
        raise ValueError("Les capacités et les journées prévues doivent correspondre.")
    modules = [(item["uv"], int(item["durationMinutes"])) for item in modules if item["durationMinutes"] > 0]
    total_minutes = sum(minutes for _, minutes in modules)
    if total_minutes != sum(preferred_minutes):
        raise ValueError("La répartition doit conserver toutes les heures APS.")
    active = [i for i, minutes in enumerate(preferred_minutes) if minutes > 0]
    if not total_minutes:
        return list(preferred_minutes)

    # Current APS durations are multiples of 30 minutes. GCD also preserves an
    # exact duration if the reference later contains a shorter teaching segment.
    step = 30
    for minutes in [m for _, m in modules] + list(capacities) + list(preferred_minutes):
        step = gcd(step, int(minutes))
    units = [uv for uv, minutes in modules for _ in range(minutes // step)]
    limits = [int(capacities[i]) // step for i in active]
    targets = [int(preferred_minutes[i]) for i in active]
    future_capacity = [0] * (len(active) + 1)
    for i in range(len(active) - 1, -1, -1):
        future_capacity[i] = future_capacity[i + 1] + limits[i]

    # Each state is an exact position in the ordered programme after a day.
    # Keeping the best path at each position makes the exception decision across
    # the whole period, instead of allowing a third UV to fill one local gap.
    layers = [{0: ((0, 0, 0, 0), None, 0)}]
    for day_index, limit in enumerate(limits):
        next_layer = {}
        days_after = len(active) - day_index - 1
        for position, (score, _, _) in layers[-1].items():
            minimum = max(1, len(units) - position - future_capacity[day_index + 1])
            maximum = min(limit, len(units) - position - days_after)
            seen = set()
            for length in range(1, maximum + 1):
                seen.add(units[position + length - 1])
                if len(seen) > 3:
                    break
                if length < minimum:
                    continue
                minutes = length * step
                candidate = (
                    score[0] + (len(seen) == 3),
                    score[1] + max(0, minutes - standard_minutes),
                    score[2] + abs(minutes - targets[day_index]),
                    score[3] + len(seen) - 1,
                )
                end = position + length
                if end not in next_layer or candidate < next_layer[end][0]:
                    next_layer[end] = (candidate, position, minutes)
        layers.append(next_layer)

    if len(units) not in layers[-1]:
        raise ValueError(
            "Impossible de répartir toutes les heures APS avec trois UV maximum "
            "par journée sur les dates disponibles. Prévoyez une période plus longue."
        )
    result = [0] * len(capacities)
    position = len(units)
    for day_index in range(len(active) - 1, -1, -1):
        _, previous, minutes = layers[day_index + 1][position]
        result[active[day_index]] = minutes
        position = previous
    return result
