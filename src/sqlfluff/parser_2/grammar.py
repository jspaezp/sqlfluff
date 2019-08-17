
import logging
from collections import namedtuple

from .segments_base import BaseSegment


class MatchResult(namedtuple('MatchResult', ['matched_segments', 'unmatched_segments'])):
    def initial_match_pos_marker(self):
        if self.has_match():
            return self.matched_segments[0].pos_marker
        else:
            return None

    def __len__(self):
        return len(self.matched_segments)

    def is_complete(self):
        return len(self) == 0

    def has_match(self):
        return len(self) > 0

    def __bool__(self):
        return self.has_match()

    def raw_matched(self):
        return ''.join([seg.raw for seg in self.matched_segments])

    def __str__(self):
        return "<MatchResult {0}/{1}: {2!r}>".format(
            len(self.matched_segments), len(self.matched_segments) + len(self.unmatched_segments),
            self.raw_matched())

    def __eq__(self, other):
        """ Equals function override, means comparison to tuples
        for testing isn't silly """
        if isinstance(other, MatchResult):
            return (self.matched_segments == other.matched_segments
                    and self.unmatched_segments == other.unmatched_segments)
        elif isinstance(other, tuple):
            return self.matched_segments == other
        elif isinstance(other, list):
            return self.matched_segments == tuple(other)
        else:
            raise TypeError(
                "Unexpected equality comparison: type: {0}".format(
                    type(other)))

    @staticmethod
    def seg_to_tuple(segs):
        if isinstance(segs, tuple):
            return segs
        if isinstance(segs, BaseSegment):
            return (segs,)
        elif isinstance(segs, list):
            return tuple(segs)
        else:
            raise ValueError("Unexpected input to `seg_to_tuple`: {0}".format(segs))

    @classmethod
    def from_unmatched(cls, unmatched):
        # NB seg_to_tuple does the type munging
        return cls(
            matched_segments=(),
            unmatched_segments=cls.seg_to_tuple(unmatched)
        )

    @classmethod
    def from_matched(cls, matched):
        # NB seg_to_tuple does the type munging
        return cls(
            unmatched_segments=(),
            matched_segments=cls.seg_to_tuple(matched)
        )

    @classmethod
    def from_empty(cls):
        return cls(unmatched_segments=(),
                   matched_segments=())

    def __add__(self, other):
        """ override + """
        if isinstance(other, BaseSegment):
            return self.__class__(
                matched_segments=self.matched_segments + (other,),
                unmatched_segments=self.unmatched_segments
            )
        elif isinstance(other, MatchResult):
            return self.__class__(
                matched_segments=self.matched_segments + other.matched_segments,
                unmatched_segments=self.unmatched_segments
            )
        elif isinstance(other, tuple):
            if len(other) > 0 and not isinstance(other[0], BaseSegment):
                raise TypeError(
                    "Unexpected type passed to MatchResult.__add__: tuple of {0}.\n{1}".format(
                        type(other[0]), other))
            return self.__class__(
                matched_segments=self.matched_segments + other,
                unmatched_segments=self.unmatched_segments
            )
        elif isinstance(other, list):
            if len(other) > 0 and not isinstance(other[0], BaseSegment):
                raise TypeError(
                    "Unexpected type passed to MatchResult.__add__: list of {0}".format(
                        type(other[0])))
            return self.__class__(
                matched_segments=self.matched_segments + tuple(other),
                unmatched_segments=self.unmatched_segments
            )
        else:
            raise TypeError(
                "Unexpected type passed to MatchResult.__add__: {0}".format(
                    type(other)))

    # def __iadd__(self, other):
    #     """ override += """
    #     # https://www.python-course.eu/python3_magic_methods.php
    #     return self


class BaseGrammar(object):
    """ Grammars are a way of composing match statements, any grammar
    must implment the `match` function. Segments can also be passed to
    most grammars. Segments implement `match` as a classmethod. Grammars
    implement it as an instance method """

    def match(self, segments, match_depth=0, parse_depth=0):
        """
            Matching can be done from either the raw or the segments.
            This raw function can be overridden, or a grammar defined
            on the underlying class.
        """
        logging.debug("MATCH: {0}".format(self))
        raise NotImplementedError("{0} has no match function implemented".format(self.__class__.__name__))

    def _match(self, segments, match_depth=0, parse_depth=0):
        """ A wrapper on the match function to do some basic validation """
        logging.info("[PD:{0} MD:{1}] {2}._match IN [ls={3}]".format(parse_depth, match_depth, self.__class__.__name__, len(segments)))
        if not isinstance(segments, (tuple, BaseSegment)):
            logging.warning(
                "{0}.match, was passed {1} rather than tuple or segment".format(
                    self.__class__.__name__, type(segments)))
            if isinstance(segments, list):
                # Let's make it a tuple for compatibility
                segments = tuple(segments)
        m = self.match(segments, match_depth=match_depth, parse_depth=parse_depth)
        if not isinstance(m, MatchResult):
            logging.warning(
                "{0}.match, returned {1} rather than MatchResult".format(
                    self.__class__.__name__, type(m)))
        logging.info("[PD:{0} MD:{1}] {2}._match OUT [m={3}]".format(parse_depth, match_depth, self.__class__.__name__, m))
        return m

    def expected_string(self):
        """ Return a String which is helpful to understand what this grammar expects """
        raise NotImplementedError(
            "{0} does not implement expected_string!".format(
                self.__class__.__name__))


class OneOf(BaseGrammar):
    """ Match any of the elements given once, if it matches
    multiple, it returns the first """
    def __init__(self, *args, **kwargs):
        self._options = args
        self.code_only = kwargs.get('code_only', True)

    def match(self, segments, match_depth=0, parse_depth=0):
        logging.debug("MATCH: {0}".format(self))
        # Match on each of the options
        matches = []
        for opt in self._options:
            m = opt._match(segments, match_depth=match_depth + 1, parse_depth=parse_depth)
            matches.append(m)

        if sum([1 if m else 0 for m in matches]) > 1:
            logging.warning("WARNING! Ambiguous match!")

        for m in matches:
            if m:
                return m
        else:
            return MatchResult.from_unmatched(segments)

    def expected_string(self):
        return " | ".join([opt.expected_string() for opt in self._options])


class GreedyUntil(BaseGrammar):
    """
    Match anything, up to but not including the given options.

    NB: To be really specific, IF the `until` clause *is* found
    then this grammar WILL NOT match, it will only match if that
    is not present.
    """
    def __init__(self, *args, **kwargs):
        self._options = args
        # `strict`, means the segment will not be matched WITHOUT
        # the ending clause. Normally, if we run out of segments,
        # then this will still match
        self.strict = kwargs.get('strict', False)
        # NB: Right now, code_only has no effect here, because we're already
        # greedy regardless of type
        self.code_only = kwargs.get('code_only', True)

    def match(self, segments, match_depth=0, parse_depth=0):
        seg_buffer = MatchResult.from_empty()
        for seg in segments:
            for opt in self._options:
                if opt._match(seg, match_depth=match_depth + 1, parse_depth=parse_depth):
                    # it's a match! Return everything up to this point
                    # NOTE: We used to return everything up until this point
                    # but that's not in keeping with how a grammar should work.
                    # We don not return ANYTHING, if the `until` clause is found
                    # with the assumption that this is either a top level grammar
                    # OR, that it's part of a sequence, and *that sequence* will retry
                    # this grammar with a shorter segment.
                    return MatchResult.from_unmatched(segments)
                else:
                    continue
            else:
                # Add this to the buffer
                seg_buffer += seg
        else:
            # We've gone through all the segments, and not found the end
            if self.strict:
                # Strict mode means this is NOT at match because we didn't find the end.
                # NOTE: The change to the return logic means that in strict mode, we will
                # NEVER match.
                return MatchResult.from_unmatched(segments)
            else:
                return seg_buffer

    def expected_string(self):
        return "..., " + " ( " + " | ".join([opt.expected_string() for opt in self._options]) + " ) "


class Sequence(BaseGrammar):
    """ Match a specific sequence of elements """
    def __init__(self, *args, **kwargs):
        self._elems = args
        self.code_only = kwargs.get('code_only', True)

    @staticmethod
    def _match_forward(segments, matcher, code_only=True, match_depth=0, parse_depth=0):
        """ sequentially match shorter and shorter forward segments
        looking for arbitrary length matches. this function deals with
        skipping non code segments.
        UPDATE: Now starts with the longest, and go shorter. That's the make things
        work for the Delimited grammar especially. Used to start short and go long."""
        # logging.debug("_match_forward: {0!r}, {1!r}".format(matcher, segments))
        # Check if the start of this sequence is code_only
        if code_only and not segments[0].is_code:
            # skip this one for matching, but add it to the match
            return (segments[0],), 1, False
        # Try decreasing lengths to match the remainder
        match_len = len(segments)
        while True:
            logging.debug("[PD:{0} MD:{1}] Forward Match (l={2}): {3}".format(parse_depth, match_depth, match_len, ''.join([seg.raw for seg in segments[:match_len]])))
            # logging.debug("_match_forward [loop]: {0!r}, {1!r}".format(matcher, segments[:match_len]))
            m = matcher._match(segments[:match_len], match_depth=match_depth + 1,
                               parse_depth=parse_depth)
            if m:
                logging.warning("Blorp: {0}".format(m))
                # deal with the matches
                # advance the counter
                if isinstance(m, BaseSegment):
                    logging.warning("{0} returned a segment not a tuple!".format(matcher))
                    return (m,), match_len, True
                else:
                    return m, match_len, True
            match_len -= 1
            if match_len <= 0:
                return None, 0, True

    def match(self, segments, match_depth=0, parse_depth=0):
        if isinstance(segments, BaseSegment):
            segments = tuple(segments)
        # logging.debug("{0}.match, inbound segments: {1!r}".format(self.__class__.__name__, segments))
        seg_idx = 0
        matched_segments = MatchResult.from_empty()
        for elem in self._elems:
            # logging.debug("{0}.match, already matched: {1!r}".format(self.__class__.__name__, matched_segments))
            # logging.debug("{0}.match, considering: {1!r}".format(self.__class__.__name__, elem))
            # logging.debug("{0}.match, seg_idx: {1!r}".format(self.__class__.__name__, seg_idx))
            while True:
                if seg_idx >= len(segments):
                    # We've run our of sequence without matching everyting:
                    return None
                # sequentially try longer segments to see if it works.
                # We do this because the matcher might also be looking for
                # a sequence rather than a singular.
                m, n, c = self._match_forward(
                    segments=segments[seg_idx:], matcher=elem, code_only=self.code_only,
                    match_depth=match_depth, parse_depth=parse_depth)
                if m is None:
                    # We've failed to match at this index
                    return None
                else:
                    logging.debug("{0}.match, found: [n={1}] {2!r}".format(self.__class__.__name__, n, m))
                    matched_segments += m
                    # Advance the counter by the length of the match
                    seg_idx += n
                    # If code only, then see if we've matched on code
                    if self.code_only:
                        if c:
                            # If code_only, and a code match, we should move on to the next element
                            break
                        else:
                            # If code_only, and not a code match, we should carry on with the same element
                            continue
                    else:
                        # If not code_only, then any match means we should advance the element
                        break
        else:
            # We've matched everything in the sequence, but we need to check FINALLY
            # if we've matched everything that was given.
            if seg_idx == len(segments):
                # If the segments get mutated we might need to do something different here
                return matched_segments
            elif self.code_only and all(not seg.is_code for seg in segments[seg_idx:]):
                # If we're only looking for code, and the only segments left are non-code
                # then be greedy
                return matched_segments + segments[seg_idx:]
            else:
                # We matched all the sequence, but the number of segments given was longer
                return None

    def expected_string(self):
        return ", ".join([opt.expected_string() for opt in self._elems])


class Delimited(Sequence):
    """ Match an arbitrary number of elements seperated by a delimiter """
    def __init__(self, *args, **kwargs):
        self._elems = args
        self.code_only = kwargs.pop('code_only', True)
        if 'delimiter' not in kwargs:
            raise ValueError("Delimited grammars require a `delimiter`")
        self.delimiter = kwargs.pop('delimiter')
        self.allow_trailing = kwargs.pop('allow_trailing', False)
        if kwargs:
            raise ValueError("Unconsumed kwargs for {0}: {1}".format(
                self.__class__.__name__,
                kwargs
            ))

    def match(self, segments, match_depth=0, parse_depth=0):
        if isinstance(segments, BaseSegment):
            segments = [segments]
        seg_idx = 0
        matched_segments = MatchResult.from_empty()
        looking_for = 'element'  # This will be `delimiter` when we find an element
        while True:
            # logging.debug("{0}.match, already matched: {1!r}".format(self.__class__.__name__, matched_segments))
            # logging.debug("{0}.match, looking for: {1!r}".format(self.__class__.__name__, looking_for))
            # logging.debug("{0}.match, seg_idx: {1!r}".format(self.__class__.__name__, seg_idx))

            if seg_idx >= len(segments):
                # We've got to the end of the segments, we can't end on a delimiter
                # unless allow_trailing is set
                if looking_for == 'element':
                    if self.allow_trailing:
                        return matched_segments
                    else:
                        return MatchResult.from_empty()
                elif looking_for == 'delimiter':
                    return matched_segments
                else:
                    raise ValueError("Unexpected looking for!")

            if looking_for == 'element':
                for elem in self._elems:
                    # logging.debug("{0}.match, considering: {1!r}".format(self.__class__.__name__, elem))
                    m, n, c = self._match_forward(
                        segments=segments[seg_idx:], matcher=elem,
                        code_only=self.code_only,
                        match_depth=match_depth,
                        parse_depth=parse_depth)
                    if m is None:
                        # We've failed to match at this index
                        continue
                    else:
                        # logging.debug("{0}.match, found: [n={1}] {2!r}".format(self.__class__.__name__, n, m))
                        matched_segments += m
                        # Advance the counter by the length of the match
                        seg_idx += n
                        # If we matched on code, then switch
                        if c:
                            looking_for = 'delimiter'
                        break
                else:
                    # Completed a loop without a match
                    # logging.debug("{0}.match, no match [elem]".format(self.__class__.__name__))
                    return MatchResult.from_empty()
            elif looking_for == 'delimiter':
                # logging.debug("{0}.match, considering: {1!r}".format(self.__class__.__name__, self.delimiter))
                m, n, c = self._match_forward(
                    segments=segments[seg_idx:], matcher=self.delimiter,
                    code_only=self.code_only,
                    match_depth=match_depth,
                    parse_depth=parse_depth)
                if m is None:
                    # We've failed to match at this index
                    # logging.debug("{0}.match, no match [delim]".format(self.__class__.__name__))
                    return MatchResult.from_empty()
                else:
                    # logging.debug("{0}.match, found: [n={1}] {2!r}".format(self.__class__.__name__, n, m))
                    matched_segments += m
                    # Advance the counter by the length of the match
                    seg_idx += n
                    # If we matched on code, then switch
                    if c:
                        looking_for = 'element'
                    # NB: No break here, because we're not looping through options
            else:
                raise ValueError("Unexpected looking for: {0!r}".format(looking_for))

    def expected_string(self):
        return " {0} ".format(self.delimiter.expected_string()).join([opt.expected_string() for opt in self._elems])


class ContainsOnly(BaseGrammar):
    """ match a sequence of segments which are only of the types,
    or only match the grammars in the list """
    def __init__(self, *args, **kwargs):
        self._options = args
        self.code_only = kwargs.get('code_only', True)

    def match(self, segments, match_depth=0, parse_depth=0):
        seg_buffer = tuple()
        for seg in segments:
            matched = False
            if self.code_only and not seg.is_code:
                # Don't worry about non-code segments
                matched = True
                seg_buffer += (seg,)
            else:
                for opt in self._options:
                    if isinstance(opt, str):
                        if seg.type == opt:
                            matched = True
                            seg_buffer += (seg,)
                            break
                    else:
                        try:
                            m = opt._match(seg, match_depth=match_depth + 1, parse_depth=parse_depth)
                        except AttributeError:
                            # it doesn't have a match method
                            continue
                        if m:
                            matched = True
                            seg_buffer += m
                            break
            if not matched:
                # logging.debug("Non Matching Segment! {0!r}".format(seg))
                # found a non matching segment:
                return None
        else:
            # Should we also be returning a raw here?
            return seg_buffer


class StartsWith(BaseGrammar):
    """ Match if the first element is the same, with configurable
    whitespace and comment handling """
    def __init__(self, target, code_only=True, **kwargs):
        self.target = target
        self.code_only = code_only
        # Implement config handling later...

    def match(self, segments, match_depth=0, parse_depth=0):
        if self.code_only:
            first_code = None
            first_code_idx = None
            for idx, seg in enumerate(segments):
                if seg.is_code:
                    first_code_idx = idx
                    first_code = seg
                    break
            else:
                return None

            match = self.target._match(segments=[first_code], match_depth=match_depth + 1, parse_depth=parse_depth)
            if match:
                # Let's actually make it a keyword segment
                # segments[first_code_idx] = match  <- can't do this on a tuple
                segments = segments[:first_code_idx] + tuple(match) + segments[first_code_idx + 1:]
                return segments
            else:
                return None
        else:
            raise NotImplementedError("Not expecting to match StartsWith and also not just code!?")
