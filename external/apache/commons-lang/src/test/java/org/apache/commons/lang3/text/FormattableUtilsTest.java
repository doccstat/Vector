/*
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The ASF licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *      https://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.apache.commons.lang3.text;

import static org.apache.commons.lang3.LangAssertions.assertIllegalArgumentException;
import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.FormattableFlags;
import java.util.Formatter;

import org.apache.commons.lang3.AbstractLangTest;
import org.apache.commons.lang3.StringUtils;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

/**
 * Tests {@link FormattableUtils}.
 */
@Deprecated
class FormattableUtilsTest extends AbstractLangTest {

    @Test
    void testAlternatePadCharacter() {
        final char pad = '_';
        assertEquals("foo", FormattableUtils.append("foo", new Formatter(), 0, -1, -1, pad).toString());
        assertEquals("fo", FormattableUtils.append("foo", new Formatter(), 0, -1, 2, pad).toString());
        assertEquals("_foo", FormattableUtils.append("foo", new Formatter(), 0, 4, -1, pad).toString());
        assertEquals("___foo", FormattableUtils.append("foo", new Formatter(), 0, 6, -1, pad).toString());
        assertEquals("_fo", FormattableUtils.append("foo", new Formatter(), 0, 3, 2, pad).toString());
        assertEquals("___fo", FormattableUtils.append("foo", new Formatter(), 0, 5, 2, pad).toString());
        assertEquals("foo_", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 4, -1, pad).toString());
        assertEquals("foo___", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 6, -1, pad).toString());
        assertEquals("fo_", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 3, 2, pad).toString());
        assertEquals("fo___", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 5, 2, pad).toString());
    }

    @Test
    void testAlternatePadCharAndEllipsis() {
        assertEquals("foo", FormattableUtils.append("foo", new Formatter(), 0, -1, -1, '_', "*").toString());
        assertEquals("f*", FormattableUtils.append("foo", new Formatter(), 0, -1, 2, '_', "*").toString());
        assertEquals("_foo", FormattableUtils.append("foo", new Formatter(), 0, 4, -1, '_', "*").toString());
        assertEquals("___foo", FormattableUtils.append("foo", new Formatter(), 0, 6, -1, '_', "*").toString());
        assertEquals("_f*", FormattableUtils.append("foo", new Formatter(), 0, 3, 2, '_', "*").toString());
        assertEquals("___f*", FormattableUtils.append("foo", new Formatter(), 0, 5, 2, '_', "*").toString());
        assertEquals("foo_", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 4, -1, '_', "*").toString());
        assertEquals("foo___", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 6, -1, '_', "*").toString());
        assertEquals("f*_", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 3, 2, '_', "*").toString());
        assertEquals("f*___", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 5, 2, '_', "*").toString());

        assertEquals("foo", FormattableUtils.append("foo", new Formatter(), 0, -1, -1, '_', "+*").toString());
        assertEquals("+*", FormattableUtils.append("foo", new Formatter(), 0, -1, 2, '_', "+*").toString());
        assertEquals("_foo", FormattableUtils.append("foo", new Formatter(), 0, 4, -1, '_', "+*").toString());
        assertEquals("___foo", FormattableUtils.append("foo", new Formatter(), 0, 6, -1, '_', "+*").toString());
        assertEquals("_+*", FormattableUtils.append("foo", new Formatter(), 0, 3, 2, '_', "+*").toString());
        assertEquals("___+*", FormattableUtils.append("foo", new Formatter(), 0, 5, 2, '_', "+*").toString());
        assertEquals("foo_", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 4, -1, '_', "+*").toString());
        assertEquals("foo___", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 6, -1, '_', "+*").toString());
        assertEquals("+*_", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 3, 2, '_', "+*").toString());
        assertEquals("+*___", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 5, 2, '_', "+*").toString());
    }

    @Test
    void testDefaultAppend() {
        assertEquals("foo", FormattableUtils.append("foo", new Formatter(), 0, -1, -1).toString());
        assertEquals("fo", FormattableUtils.append("foo", new Formatter(), 0, -1, 2).toString());
        assertEquals(" foo", FormattableUtils.append("foo", new Formatter(), 0, 4, -1).toString());
        assertEquals("   foo", FormattableUtils.append("foo", new Formatter(), 0, 6, -1).toString());
        assertEquals(" fo", FormattableUtils.append("foo", new Formatter(), 0, 3, 2).toString());
        assertEquals("   fo", FormattableUtils.append("foo", new Formatter(), 0, 5, 2).toString());
        assertEquals("foo ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 4, -1).toString());
        assertEquals("foo   ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 6, -1).toString());
        assertEquals("fo ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 3, 2).toString());
        assertEquals("fo   ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 5, 2).toString());
    }

    @Test
    void testEllipsis() {
        assertEquals("foo", FormattableUtils.append("foo", new Formatter(), 0, -1, -1, "*").toString());
        assertEquals("f*", FormattableUtils.append("foo", new Formatter(), 0, -1, 2, "*").toString());
        assertEquals(" foo", FormattableUtils.append("foo", new Formatter(), 0, 4, -1, "*").toString());
        assertEquals("   foo", FormattableUtils.append("foo", new Formatter(), 0, 6, -1, "*").toString());
        assertEquals(" f*", FormattableUtils.append("foo", new Formatter(), 0, 3, 2, "*").toString());
        assertEquals("   f*", FormattableUtils.append("foo", new Formatter(), 0, 5, 2, "*").toString());
        assertEquals("foo ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 4, -1, "*").toString());
        assertEquals("foo   ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 6, -1, "*").toString());
        assertEquals("f* ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 3, 2, "*").toString());
        assertEquals("f*   ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 5, 2, "*").toString());

        assertEquals("foo", FormattableUtils.append("foo", new Formatter(), 0, -1, -1, "+*").toString());
        assertEquals("+*", FormattableUtils.append("foo", new Formatter(), 0, -1, 2, "+*").toString());
        assertEquals(" foo", FormattableUtils.append("foo", new Formatter(), 0, 4, -1, "+*").toString());
        assertEquals("   foo", FormattableUtils.append("foo", new Formatter(), 0, 6, -1, "+*").toString());
        assertEquals(" +*", FormattableUtils.append("foo", new Formatter(), 0, 3, 2, "+*").toString());
        assertEquals("   +*", FormattableUtils.append("foo", new Formatter(), 0, 5, 2, "+*").toString());
        assertEquals("foo ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 4, -1, "+*").toString());
        assertEquals("foo   ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 6, -1, "+*").toString());
        assertEquals("+* ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 3, 2, "+*").toString());
        assertEquals("+*   ", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, 5, 2, "+*").toString());
    }

    @ParameterizedTest
    @ValueSource(ints = {0, FormattableFlags.LEFT_JUSTIFY})
    void testEmptyPadding(final int flags) {
        assertEquals("_____", FormattableUtils.append("", new Formatter(), flags, 5, -1, '_').toString());
        assertEquals("_____", FormattableUtils.append("foo", new Formatter(), flags, 5, 0, '_').toString());
    }

    @Test
    void testIllegalEllipsis() {
        assertIllegalArgumentException(() -> FormattableUtils.append("foo", new Formatter(), 0, -1, 1, "xx"));
    }

    @ParameterizedTest
    @ValueSource(ints = {0, FormattableFlags.LEFT_JUSTIFY})
    void testLargePadding(final int flags) {
        final int width = 500_000;
        final String padding = StringUtils.repeat(' ', width - 3);
        final String expected = flags == 0 ? padding + "foo" : "foo" + padding;
        assertEquals(expected, FormattableUtils.append("foo", new Formatter(), flags, width, -1).toString());
    }

    @ParameterizedTest
    @ValueSource(ints = {0, FormattableFlags.LEFT_JUSTIFY})
    void testLargePaddingWithEllipsis(final int flags) {
        final int width = 500_000;
        final String padding = StringUtils.repeat('\u2603', width - 3);
        final String expected = flags == 0 ? padding + "fo*" : "fo*" + padding;
        assertEquals(expected, FormattableUtils.append("foobar", new Formatter(), flags, width, 3, '\u2603', "*").toString());
    }

    @ParameterizedTest
    @ValueSource(ints = {Integer.MIN_VALUE, -1, 0, 2, 3})
    void testNoPadding(final int width) {
        assertEquals("foo", FormattableUtils.append("foo", new Formatter(), 0, width, -1).toString());
        assertEquals("foo", FormattableUtils.append("foo", new Formatter(), FormattableFlags.LEFT_JUSTIFY, width, -1).toString());
    }

    @Test
    void testPercentLiteral() {
        assertEquals("100% done", FormattableUtils.append("100% done", new Formatter(), 0, -1, -1).toString());
    }

    @Test
    void testPercentLiteralX2() {
        assertEquals("50% off 100% items", FormattableUtils.append("50% off 100% items", new Formatter(), 0, -1, -1).toString());
    }

}
