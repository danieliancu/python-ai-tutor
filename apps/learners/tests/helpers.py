from itertools import count

from apps.curriculum.models import World

_sequence = count(1)


def make_world(title: str = "", is_published: bool = True, **fields) -> World:
    n = next(_sequence)
    return World.objects.create(
        title=title or f"World {n}",
        slug=fields.pop("slug", f"world-{n}"),
        description=fields.pop("description", f"Learn topic number {n}."),
        order=fields.pop("order", 500 + n),
        is_published=is_published,
        **fields,
    )
