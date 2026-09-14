const { Tool } = require('@librechat/agents/langchain/tools');
const { z } = require('zod');

class InternalData extends Tool {
  constructor(options = {}) {
    super(options);

    this.name = 'internal_data';

    this.description =
      "Retrieve information from Prarambha's local internal data source.";

    this.schema = z.object({
      query: z
        .string()
        .min(1)
        .describe(
          'The information to retrieve from the internal data source.',
        ),
    });
  }

  async _call({ query }) {
    const response = await fetch(
      'http://host.docker.internal:9000/tools/internal-data',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      },
    );

    if (!response.ok) {
      throw new Error(
        `Internal data service returned HTTP ${response.status}`,
      );
    }

    return await response.text();
  }
}

module.exports = InternalData;
