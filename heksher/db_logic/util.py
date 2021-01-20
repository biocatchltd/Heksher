import re
from typing import Collection, Tuple, TypeVar, Sequence, Hashable, Dict, Union

T = TypeVar('T', bound=Hashable)


# pytype: disable=not-supported-yet
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


# pytype: enable=not-supported-yet

INLINE_VALIDATION_PATTERN = re.compile(r'[a-zA-Z0-9_\s]+')


def inline_sql(x: str) -> str:
    """
    Wrap a string, that is about to be inlined into an SQL query as a string literal, or raise an exception if it is
    invalid
    Args:
        x: The string to be validated
    Returns:
        x wrapped in single quotes
    Raises:
        AssertionError if the string is invalid
    Notes:
        This function should be used as a means of assertion, api validation must be done before calling.
        The validation of this method is especially stringent, since the string is inlined into a query. many safe SQL
         strings will be rejected here.
    """
    if not INLINE_VALIDATION_PATTERN.fullmatch(x):
        raise AssertionError(f'string {x!r} cannot be inlined')
    return f"'{x}'"
