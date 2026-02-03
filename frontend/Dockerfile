FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 8080

# Run development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "8080"]
