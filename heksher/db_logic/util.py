import re
from typing import Collection, Dict, Hashable, Sequence, Tuple, TypeVar, Union

T = TypeVar('T', bound=Hashable)


def supersequence_new_elements(supersequence: Sequence[T], subsequence: Collection[T]) \
        -> Union[Collection[Tuple[T, int]], None]:
    """
    Check whether a sequence is a supersequence of another sequence
    Args:
        supersequence: the sequence to assert is a supersequence
        subsequence: the collection to assert is a subsequence
    Returns:
        None if the sequences are not super-sub, or a collection of the new items in the supersequence
    Note:
        supersequence should be non-repeating, and subsequence should be well-ordered
    """
    new_elements: Dict[T, int] = {}

    # an iterator over the sub-sequence
    sub_iterator = iter(subsequence)
    try:
        next_expected_element = next(sub_iterator)
    except StopIteration:
        # the sub-sequence is empty, therefore all members in the supersequence are new
        i = -1
    else:
        # i will store the last index in the super that has been properly consumed
        for i, element in enumerate(supersequence):
            # since the supersequence is non-repeating, we can assume that any match to the next expected element is a
            # part of the sub-sequence
            if element == next_expected_element:
                try:
                    next_expected_element = next(sub_iterator)
                except StopIteration:
                    # the sub-sequence has been fully consumed
                    break
            else:
                new_elements[element] = i
        else:
            # supersequence is out of elements but subsequence still has some (therefore, it is not a subsequence)
            return None

    # subsequence has been consumed, everything left in super is new
    new_elements.update(
        (k, j) for (j, k) in enumerate(supersequence[i + 1:], i + 1)
    )
    return tuple(new_elements.items())


INLINE_VALIDATION_PATTERN = re.compile(r'[a-zA-Z0-9_\s]+')
