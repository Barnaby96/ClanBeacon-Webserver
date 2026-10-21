from decimal import Decimal
from functools import lru_cache

def maximise_board_points_from_plans(budgets, plans):
    """Maximise completed points within shared character-hours."""
    players = tuple(budgets)
    initial = tuple(Decimal(str(budgets[p])) for p in players)
    tiles = tuple(plans)

    @lru_cache(maxsize=None)
    def search(index, remaining):
        if index == len(tiles):
            return 0
        tile = tiles[index]
        highest = search(index + 1, remaining)
        for option in tile["options"]:
            if set(option) - set(players):
                raise ValueError("Unknown character allocation.")
            costs = tuple(Decimal(str(option.get(p, 0))) for p in players)
            if all(0 <= cost <= left for cost, left in zip(costs, remaining)):
                next_hours = tuple(left - cost for left, cost in zip(remaining, costs))
                highest = max(highest, tile["points"] + search(index + 1, next_hours))
        return highest

    return search(0, initial)
