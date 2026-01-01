export class ImpulsesError extends Error {
  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

export class AuthenticationError extends ImpulsesError {}
export class AuthorizationError extends ImpulsesError {}
export class NotFoundError extends ImpulsesError {}
export class ValidationError extends ImpulsesError {}
export class ServerError extends ImpulsesError {}
export class NetworkError extends ImpulsesError {}
