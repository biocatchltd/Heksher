import re
from typing import NamedTuple, Collection, Tuple, TypeVar, Generic, Sequence, Hashable, Dict, Union, Literal

T = TypeVar('T', bound=Hashable)


# pytype: disable=not-supported-yet

class SupersequenceResults(NamedTuple, Generic[T]):
    """
    An object returned by is_supersequence to denote that the supersequence matches, along with the elements in the
    supersequence that are missing from the subsequence
    """
    new_elements: Collection[Tuple[T, int]]


def is_supersequence(supersequence: Sequence[T], subsequence: Collection[T]) \
        -> Union[SupersequenceResults, Literal[False]]:
    """
    Check whether a sequence is a supersequence of another sequence
    Args:
        supersequence: the sequence to assert is a supersequence
        subsequence: the collection to assert is a subsequence
    Returns:
        False if the sequences are not super-sub, or SupersequenceResults if they are
    Note:
        supersequence should be non-repeating
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
            return False

    # subsequence has been consumed, everything left in super is new
    new_elements.update(
        (k, j) for (j, k) in enumerate(supersequence[i + 1:], i + 1)
    )
    return SupersequenceResults(tuple(new_elements.items()))


# pytype: enable=not-supported-yet

INLINE_VALIDATION_PATTERN = re.compile(r'[a-zA-Z0-9_\s]+')


def inline_sql(x: str) -> str:
    """
    Wrap a string, that is about to be inlined into an SQL query as a string literal, or raise an exception if it invalid
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
