import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { askAboutPlant, userMessage } from '../services/geminiService';
import { reportAi } from './OfflineNotice';
import SourceLine from './SourceLine';
import { COLORS, FONTS, TYPE, LINE } from '../theme';

const MAX_LENGTH = 200;
const SUGGESTIONS = {
  invasive: ['Why is it a problem?', 'How do I remove it safely?', 'Is it safe for pets?'],
  other: ['What wildlife does it help?', 'How big does it get?', 'Is it safe for pets?'],
};

function uniqueSources(sources) {
  const seen = new Set();
  return sources.filter(s => s?.name && !seen.has(s.name + s.url) && seen.add(s.name + s.url));
}

const sourceKey = sentence => uniqueSources(sentence.sources).map(s => s.name + s.url).join('|');

export default function PlantQuestion({ scientificName, status, zipCode }) {
  const [question, setQuestion] = useState('');
  const [asked, setAsked] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const ready = question.trim().length >= 3 && !loading;

  async function ask(text) {
    const q = text.trim();
    if (q.length < 3 || loading) return;
    setQuestion(q); setAsked(q); setLoading(true); setError(null); setResult(null);
    try {
      const data = await askAboutPlant(scientificName, q, zipCode);
      setResult(data.result);
      reportAi(data.result.ai_unavailable);
    } catch (err) {
      setError(userMessage(err, 'Could not get an answer. Check your connection and try again.'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.card}>
      <Text accessibilityRole="header" style={styles.title}>Ask about this plant</Text>
      <Text style={styles.note}>Answers come only from our plant records. Each sentence shows where it came from.</Text>

      <View style={styles.suggestions}>
        {(SUGGESTIONS[status] ?? SUGGESTIONS.other).map(s => (
          <TouchableOpacity key={s} accessibilityRole="button" disabled={loading} style={styles.suggestion} onPress={() => ask(s)}>
            <Text style={styles.suggestionText}>{s}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={styles.inputRow}>
        <TextInput
          accessibilityLabel="Your question about this plant"
          placeholder="Type your own question"
          placeholderTextColor={COLORS.textMuted}
          value={question}
          onChangeText={setQuestion}
          onSubmitEditing={() => ask(question)}
          maxLength={MAX_LENGTH}
          returnKeyType="send"
          editable={!loading}
          style={styles.input}
        />
        <TouchableOpacity accessibilityRole="button" accessibilityLabel="Ask" accessibilityState={{ disabled: !ready, busy: loading }}
          disabled={!ready} style={[styles.askBtn, !ready && styles.askBtnDisabled]} onPress={() => ask(question)}>
          {loading
            ? <ActivityIndicator color={COLORS.onDark} size="small" />
            : <MaterialCommunityIcons name="send" size={20} color={COLORS.onDark} />}
        </TouchableOpacity>
      </View>

      {error && <Text accessibilityLiveRegion="assertive" style={styles.error}>{error}</Text>}

      {result && (
        <View style={styles.answer} accessibilityLiveRegion="polite">
          <Text style={styles.asked}>{asked}</Text>
          {result.answer.map((sentence, i) => (
            <View key={i} style={styles.sentence}>
              <Text style={styles.sentenceText}>{sentence.text}</Text>
              {sourceKey(sentence) !== (result.answer[i + 1] && sourceKey(result.answer[i + 1]))
                && uniqueSources(sentence.sources).map(source => <SourceLine key={source.name + source.url} source={source} />)}
            </View>
          ))}
          {result.message && <Text style={styles.message}>{result.message}</Text>}
          {result.message && result.records.length > 0 && (
            <View style={styles.records}>
              {result.records.map(record => (
                <View key={record.id} style={styles.record}>
                  <Text style={styles.recordText}>{record.text}</Text>
                  <SourceLine source={record.source} />
                </View>
              ))}
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: 16, gap: 12, backgroundColor: COLORS.cardBg, borderWidth: 1, borderColor: COLORS.border, borderRadius: 16, padding: 20 },
  title: { fontSize: TYPE.h3, lineHeight: LINE.h3, fontFamily: FONTS.heading, color: COLORS.darkGreen },
  note: { fontSize: TYPE.caption, lineHeight: LINE.caption, fontFamily: FONTS.body, color: COLORS.textMuted },
  suggestions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  suggestion: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 14, borderRadius: 22, backgroundColor: COLORS.lightBg },
  suggestionText: { fontSize: TYPE.caption, fontFamily: FONTS.bodyBold, color: COLORS.darkGreen },
  inputRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  input: {
    flex: 1, minWidth: 0, minHeight: 48, borderWidth: 1, borderColor: COLORS.border, borderRadius: 12, paddingHorizontal: 14,
    backgroundColor: COLORS.white, fontSize: TYPE.body, fontFamily: FONTS.body, color: COLORS.textBody,
  },
  askBtn: { width: 48, height: 48, borderRadius: 12, backgroundColor: COLORS.darkGreen, alignItems: 'center', justifyContent: 'center' },
  askBtnDisabled: { opacity: 0.4 },
  error: { fontSize: TYPE.body, lineHeight: LINE.body, fontFamily: FONTS.body, color: COLORS.error },
  answer: { gap: 14, paddingTop: 4 },
  asked: { fontSize: TYPE.caption, lineHeight: LINE.caption, fontFamily: FONTS.bodyBold, color: COLORS.textMuted },
  sentence: { gap: 2, paddingLeft: 12, borderLeftWidth: 3, borderLeftColor: COLORS.softGreen },
  sentenceText: { fontSize: TYPE.body, lineHeight: LINE.body, fontFamily: FONTS.body, color: COLORS.textBody },
  message: { fontSize: TYPE.body, lineHeight: LINE.body, fontFamily: FONTS.bodyMedium, color: COLORS.textBody },
  records: { gap: 12 },
  record: { gap: 2 },
  recordText: { fontSize: TYPE.caption, lineHeight: LINE.caption, fontFamily: FONTS.body, color: COLORS.textBody },
});
