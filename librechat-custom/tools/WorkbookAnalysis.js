const { Tool } = require('@librechat/agents/langchain/tools');
const { z } = require('zod');

class WorkbookAnalysis extends Tool {
  constructor(options = {}) {
    super(options);

    this.name = 'workbook_analysis';

    this.description =
      "Analyze the latest company Excel workbook using the internal Python analysis service. Use this tool when the user asks to inspect, analyze, audit, summarize, or find anomalies in a company Excel workbook. The tool result is the authoritative source of truth. Only report facts, anomaly counts, values, sheet names, column names, and findings explicitly present in the returned result. Do not infer, guess, extrapolate, or invent specific records, values, causes, impacts, or examples that are not explicitly returned by the tool. If the result does not contain enough information to support a claim, say that the information is not available. Clearly distinguish tool-reported findings from general recommendations.";

    this.schema = z.object({
      filename: z
        .string()
        .optional()
        .describe(
          'Optional Excel filename. If omitted, analyze the latest .xlsx workbook in the incoming data directory.',
        ),
    });
  }

  async _call({ filename }) {
    const response = await fetch(
      'http://host.docker.internal:9000/tools/analyze-workbook',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(
          filename && filename.trim()
            ? { filename: filename.trim() }
            : {},
        ),
      },
    );

    if (!response.ok) {
      throw new Error(
        `Workbook analysis service returned HTTP ${response.status}`,
      );
    }

    return await response.text();
  }
}

module.exports = WorkbookAnalysis;
