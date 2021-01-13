from typing import NamedTuple, Collection, Tuple, TypeVar, Generic, Sequence, Hashable, Dict, Union, Literal

T = TypeVar('T', bound=Hashable)


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
        subsequence: the sequence to assert is a subsequence
    Returns:
        False if the sequences are not super-sub, or SupersequenceResults if they are
    Note:
        supersequence should be non-repeating
    """
    new_elements: Dict[T, int] = {}

    sub_iterator = iter(subsequence)
    try:
        next_expected_element = next(sub_iterator)
    except StopIteration:
        i = -1
    else:
        for i, element in enumerate(supersequence):
            if element == next_expected_element:
                try:
                    next_expected_element = next(sub_iterator)
                except StopIteration:
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
